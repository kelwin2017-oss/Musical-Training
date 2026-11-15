"""Servidor local do Treino de Letras.

Serve a pasta em http://localhost:8765 (só no seu PC) e abre o navegador.
O YouTube só deixa o player incorporado funcionar em páginas http(s),
por isso o app precisa rodar por aqui e não com duplo-clique no index.html.

Todos os seus dados ficam na pasta `dados/` ao lado deste arquivo:
  dados/songs.json     músicas (título, artista, capa, letra, sincronia, melhores %)
  dados/words.json     palavras da revisão espaçada
  dados/history.json   histórico de partidas (XP, sequência, gráficos)
  dados/settings.json  configurações
  dados/midia/         cópias dos arquivos de áudio/vídeo que você escolheu do PC
  dados/backups/       cópia automática diária dos .json (guarda os últimos 14 dias)
Para levar tudo para outro PC, basta copiar a pasta inteira do app.

Também oferece 3 rotas auxiliares (o navegador não consegue acessar esses
sites direto por causa de CORS):
  /api/playlist?list=ID   -> vídeos de uma playlist do YouTube (id, título, canal, duração)
  /api/oembed?id=VIDEO    -> título e canal de um vídeo
  /api/itunes?term=TEXTO  -> busca de capa no iTunes
  /api/captions?id=VIDEO&lang=en -> legendas do vídeo (para sincronizar a letra com o clipe)
"""
import http.server
import json
import os
import re
import select
import shutil
import socketserver
import subprocess
import time
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
ROOT = os.path.dirname(os.path.abspath(__file__))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


DATA = os.path.join(ROOT, "dados")
MEDIA = os.path.join(DATA, "midia")
BACKUPS = os.path.join(DATA, "backups")
STORES = ("songs", "words", "history", "settings", "meta")
KEYS = {"words": "key"}  # chave de cada registro (o resto usa "id")
LOCK = threading.RLock()
_cache = {}
_backup_day = None


# ---------------------------------------------------------------- log e modo sem janela
BACKGROUND = sys.stdout is None or os.path.basename(sys.executable).lower().startswith("pythonw")


def _setup_log():
    """Sem janela (pythonw), as mensagens vão para dados/servidor.log."""
    if not BACKGROUND:
        return
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, "servidor.log")
    try:
        if os.path.getsize(path) > 1024 * 1024:  # guarda só o último ~1 MB
            _replace(path, path + ".old") if os.path.exists(path) else None
    except OSError:
        pass
    f = open(path, "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = f


def log(msg):
    try:
        print(time.strftime("%d/%m %H:%M:%S ") + msg, flush=True)
    except Exception:
        pass


# ---------------------------------------------------------------- encerramento automático
# Sem janela, o servidor vive enquanto houver uma aba do app aberta. Cada aba mantém uma
# conexão aberta em /api/alive; quando a última fecha (aba ou navegador fechado), ele encerra.
TAB_GRACE = 15       # última aba fechou: espera 15 s (dá tempo de recarregar a página) e encerra
STARTUP_WAIT = 120   # ao abrir: espera até 2 min pela primeira aba
_tabs = 0
_tabs_ever = False
_empty_since = time.time()
_tabs_lock = threading.Lock()
_httpd = None


def _tab_open():
    global _tabs, _tabs_ever
    with _tabs_lock:
        _tabs += 1
        _tabs_ever = True


def _tab_closed():
    global _tabs, _empty_since
    with _tabs_lock:
        _tabs -= 1
        if _tabs <= 0:
            _tabs = 0
            _empty_since = time.time()


def _shutdown(reason):
    log(f"Encerrando o servidor ({reason}).")
    if _httpd:
        threading.Thread(target=_httpd.shutdown, daemon=True).start()


def _watchdog():
    global _empty_since
    prev = time.time()
    while True:
        time.sleep(2)
        now = time.time()
        if now - prev > 30:      # o PC estava dormindo: dá tempo para a aba reconectar
            _empty_since = now
        prev = now
        if _tabs > 0:
            continue
        if now - _empty_since > (TAB_GRACE if _tabs_ever else STARTUP_WAIT):
            return _shutdown("a aba do app foi fechada" if _tabs_ever else "nenhuma aba do app abriu")


def _update_ytdlp():
    """Atualiza o yt-dlp uma vez por semana, em segundo plano (o YouTube muda e ele precisa acompanhar)."""
    mark = os.path.join(DATA, ".ytdlp-update")
    try:
        if os.path.exists(mark) and time.time() - os.path.getmtime(mark) < 7 * 86400:
            return
        py = sys.executable
        if py.lower().endswith("pythonw.exe"):
            py = py[:-5] + ".exe"   # pip precisa do python.exe
        flags = 0x08000000 if sys.platform.startswith("win") else 0   # CREATE_NO_WINDOW
        r = subprocess.run([py, "-m", "pip", "install", "--user", "-U", "-q", "--disable-pip-version-check", "yt-dlp"],
                           capture_output=True, text=True, timeout=300, creationflags=flags)
        if r.returncode == 0:
            os.makedirs(DATA, exist_ok=True)
            open(mark, "w").close()
            log("yt-dlp atualizado.")
        else:
            log("Não consegui atualizar o yt-dlp: " + (r.stderr or "").strip()[-200:])
    except Exception as e:
        log(f"Não consegui atualizar o yt-dlp: {type(e).__name__}: {e}")


# ---------------------------------------------------------------- armazenamento em arquivo
def _replace(src, dst):
    """os.replace com novas tentativas: no Windows o OneDrive/antivírus às vezes trava o arquivo por um instante."""
    for i in range(25):
        try:
            return os.replace(src, dst)
        except PermissionError:
            time.sleep(0.08 * (i + 1))
    os.replace(src, dst)


def _copy_quiet(src, dst):
    try:
        shutil.copy2(src, dst)
    except OSError:
        pass


def _json_path(store):
    return os.path.join(DATA, f"{store}.json")


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load(store):
    with LOCK:
        if store not in _cache:
            path = _json_path(store)
            data = {}
            if os.path.exists(path):
                try:
                    data = _read_json(path)
                except (json.JSONDecodeError, OSError):
                    # arquivo corrompido: guarda uma cópia e tenta a versão anterior
                    shutil.copy2(path, path + f".corrompido-{int(time.time())}")
                    try:
                        data = _read_json(path + ".bak")
                    except Exception:
                        data = {}
            _cache[store] = data if isinstance(data, dict) else {}
        return _cache[store]


def _daily_backup():
    global _backup_day
    today = time.strftime("%Y-%m-%d")
    if _backup_day == today:
        return
    dest = os.path.join(BACKUPS, today)
    if os.path.isdir(dest):
        _backup_day = today
    else:
        files = [f for f in os.listdir(DATA) if f.endswith(".json")] if os.path.isdir(DATA) else []
        if files:  # só marca o dia quando há algo para copiar
            os.makedirs(dest, exist_ok=True)
            for f in files:
                _copy_quiet(os.path.join(DATA, f), os.path.join(dest, f))
            _backup_day = today
    if os.path.isdir(BACKUPS):  # mantém só os 14 dias mais recentes
        days = sorted(d for d in os.listdir(BACKUPS) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d))
        for d in days[:-14]:
            shutil.rmtree(os.path.join(BACKUPS, d), ignore_errors=True)


def save(store):
    with LOCK:
        os.makedirs(DATA, exist_ok=True)
        _daily_backup()
        path = _json_path(store)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache[store], f, ensure_ascii=False, indent=1)
        if os.path.exists(path):
            _copy_quiet(path, path + ".bak")
        _replace(tmp, path)


def load_media_index():
    with LOCK:
        if "_media" not in _cache:
            p = os.path.join(MEDIA, "_index.json")
            try:
                _cache["_media"] = _read_json(p)
            except Exception:
                _cache["_media"] = {}
        return _cache["_media"]


def save_media_index():
    with LOCK:
        os.makedirs(MEDIA, exist_ok=True)
        p = os.path.join(MEDIA, "_index.json")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(_cache["_media"], f, ensure_ascii=False, indent=1)
        _replace(p + ".tmp", p)


def folder_size(path):
    total = 0
    for dp, _, fs in os.walk(path):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def open_folder(path):
    os.makedirs(path, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)  # noqa
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------- HTTP util
def http_get(url, data=None, headers=None, timeout=20):
    h = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
         "Cookie": "SOCS=CAI; CONSENT=YES+1"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def walk(obj, key, out):
    """Coleta todos os valores de `key` em qualquer profundidade do JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                out.append(v)
            else:
                walk(v, key, out)
    elif isinstance(obj, list):
        for v in obj:
            walk(v, key, out)
    return out


def text_of(x):
    if not isinstance(x, dict):
        return ""
    if "simpleText" in x:
        return x["simpleText"]
    return "".join(r.get("text", "") for r in x.get("runs", []))


# ---------------------------------------------------------------- YouTube
def _extract(data):
    items = []
    for v in walk(data, "playlistVideoRenderer", []):
        vid = v.get("videoId")
        title = text_of(v.get("title"))
        if not vid or v.get("isPlayable") is False or title in ("[Deleted video]", "[Private video]"):
            continue
        try:
            dur = int(v.get("lengthSeconds") or 0) or None
        except ValueError:
            dur = None
        items.append({"id": vid, "title": title, "channel": text_of(v.get("shortBylineText")), "duration": dur})
    token = None
    for c in walk(data, "continuationItemRenderer", []):
        for cmd in walk(c, "continuationCommand", []):
            if isinstance(cmd, dict) and cmd.get("token"):
                token = cmd["token"]
    return items, token


def yt_playlist(list_id):
    html = http_get(f"https://www.youtube.com/playlist?list={list_id}&hl=en")
    m = (re.search(r"var ytInitialData\s*=\s*(\{.*?\});\s*</script>", html, re.S)
         or re.search(r'window\["ytInitialData"\]\s*=\s*(\{.*?\});', html, re.S))
    if not m:
        raise ValueError("não encontrei os dados da playlist (ela é privada?)")
    data = json.loads(m.group(1))
    meta = walk(data, "playlistMetadataRenderer", [])
    title = meta[0].get("title", "") if meta else ""
    items, token = _extract(data)
    ver = re.search(r'"INNERTUBE_CLIENT_VERSION":"([^"]+)"', html)
    key = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    pages = 0
    while token and ver and pages < 50:  # playlists grandes vêm em páginas de 100
        pages += 1
        body = json.dumps({"context": {"client": {"clientName": "WEB", "clientVersion": ver.group(1), "hl": "en"}},
                           "continuation": token}).encode()
        url = "https://www.youtube.com/youtubei/v1/browse?prettyPrint=false" + (f"&key={key.group(1)}" if key else "")
        try:
            more, token = _extract(json.loads(http_get(url, data=body, headers={"Content-Type": "application/json"})))
        except Exception:
            break
        if not more:
            break
        items += more
    seen, uniq = set(), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            uniq.append(it)
    return {"title": title, "items": uniq}


def yt_oembed(vid):
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}")
    d = json.loads(http_get(url))
    return {"title": d.get("title", ""), "author_name": d.get("author_name", "")}


def _json_after(text, marker):
    """Lê o objeto JSON que vem logo depois de `marker` (ex.: ytInitialPlayerResponse = {...})."""
    i = text.find(marker)
    if i < 0:
        return None
    i = text.find("{", i)
    try:
        return json.JSONDecoder().raw_decode(text, i)[0]
    except ValueError:
        return None


def _caption_tracks(vid):
    """Faixas de legenda do vídeo: primeiro a página normal (rápida); se não servir, o yt-dlp."""
    found = []
    try:
        html = http_get(f"https://www.youtube.com/watch?v={vid}&hl=en&bpctr=9999999999&has_verified=1")
        pr = _json_after(html, "ytInitialPlayerResponse")
        found = (((pr or {}).get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks") or []
    except Exception:
        pass
    if found:
        yield "web", found
    # o yt-dlp acompanha as mudanças do YouTube e costuma funcionar quando a página não serve
    try:
        tr = _ytdlp_tracks(vid)
        if tr:
            yield "yt-dlp", tr
    except Exception as e:
        log(f"[legendas] {vid}: yt-dlp falhou ({type(e).__name__}: {str(e)[:120]})")


def _ytdlp_tracks(vid):
    try:
        import yt_dlp  # noqa
    except ImportError:
        return []
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "logger": _QuietLog()}) as y:
        info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
    out = []
    for kind, src in (("", info.get("subtitles") or {}), ("asr", info.get("automatic_captions") or {})):
        for code, fmts in src.items():
            for f in fmts or []:
                if f.get("ext") == "json3" and f.get("url"):
                    out.append({"languageCode": code.replace("-orig", ""), "kind": kind, "baseUrl": f["url"]})
    return out


class _QuietLog:
    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


def _parse_json3(d):
    cues = []
    for e in d.get("events", []):
        segs = e.get("segs")
        if not segs:
            continue
        t0 = (e.get("tStartMs") or 0) / 1000
        dur = (e.get("dDurationMs") or 0) / 1000
        text, words = "", []
        for sg in segs:
            u = sg.get("utf8", "")
            text += u
            w = u.strip()
            if w and w[0] not in "[(♪":   # pula marcações como [Música], [Aplausos], ♪
                words.append({"t": round(t0 + (sg.get("tOffsetMs") or 0) / 1000, 3), "w": w})
        text = re.sub(r"[\[(][^\])]*[\])]", " ", text).replace("♪", " ")
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            cues.append({"t": round(t0, 3), "d": round(dur, 3), "text": text, "words": words})
    return cues


NO_CAPTION_TTL = 3 * 86400  # tenta de novo um vídeo "sem legenda" só depois de 3 dias (ou na hora, pelo 🤖 Auto)


def _write_cache(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        _replace(path + ".tmp", path)
    except OSError:
        pass


def yt_captions(vid, lang, force=False):
    lang = (lang or "en").lower()[:5]
    cache = os.path.join(DATA, "legendas", f"{vid}_{lang}.json")
    if os.path.exists(cache):
        try:
            c = _read_json(cache)
            if "cues" in c:
                return c
            if not force and time.time() - c.get("at", 0) < NO_CAPTION_TTL:
                raise ValueError(c.get("error") or "este vídeo não tem legenda disponível")
        except ValueError:
            raise
        except Exception:
            pass
    try:
        res = _yt_captions(vid, lang)
    except ValueError as e:
        log(f"[legendas] {vid}: sem legenda útil — {e}")
        _write_cache(cache, {"error": str(e), "at": time.time()})
        raise
    log(f"[legendas] {vid}: ok ({res['origin']}, {res['lang']}{', automática' if res['kind'] == 'asr' else ''})")
    _write_cache(cache, res)
    return res


def _yt_captions(vid, lang):
    errors = []
    for origin, tracks in _caption_tracks(vid):
        def rank(tr):
            code = (tr.get("languageCode") or "").lower()
            same = code == lang or code.startswith(lang + "-") or code.split("-")[0] == lang
            auto = tr.get("kind") == "asr"
            return (0 if same else 2) + (1 if auto else 0)
        for tr in sorted(tracks, key=rank):
            if rank(tr) >= 2:  # só legendas no idioma da música (o texto precisa bater com a letra)
                break
            url = tr.get("baseUrl") or ""
            url = re.sub(r"&fmt=[^&]*", "", url) + "&fmt=json3"
            try:
                raw = http_get(url)
                cues = _parse_json3(json.loads(raw)) if raw.strip() else []
            except Exception as e:
                errors.append(f"{origin}: {type(e).__name__}")
                continue
            if cues:
                return {"kind": "asr" if tr.get("kind") == "asr" else "manual",
                        "lang": tr.get("languageCode"), "origin": origin, "cues": cues}
            errors.append(f"{origin}: legenda vazia")
    errors = list(dict.fromkeys(errors))
    try:
        import yt_dlp  # noqa
        hint = ""
    except ImportError:
        hint = " — dica: instale o yt-dlp (o iniciar.bat faz isso) para mais vídeos funcionarem"
    raise ValueError("este vídeo não tem legenda disponível no idioma da música" + (f" ({'; '.join(errors)})" if errors else "") + hint)


def itunes(term, country):
    q = urllib.parse.urlencode({"term": term, "entity": "song", "limit": "8", "country": country})
    return json.loads(http_get("https://itunes.apple.com/search?" + q))


# ---------------------------------------------------------------- servidor
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # silencioso

    # Só aceita chamadas do próprio app (evita que outro site aberto no navegador mexa nos seus dados)
    def _trusted(self):
        host = (self.headers.get("Host") or "").lower()
        ok_hosts = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}
        if host not in ok_hosts:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin.lower() in {f"http://{h}" for h in ok_hosts}

    def _body(self, limit=50 * 1024 * 1024):
        n = int(self.headers.get("Content-Length") or 0)
        if n > limit:
            raise ValueError("conteúdo grande demais")
        return self.rfile.read(n) if n else b""

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _alive(self):
        """Conexão aberta enquanto a aba existir (Server-Sent Events). Quando a aba ou o
        navegador fecha, a conexão cai e o servidor fica sabendo na hora."""
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        sock = self.connection
        _tab_open()
        try:
            self.wfile.write(("retry: 2000\ndata: " + json.dumps({"background": BACKGROUND}) + "\n\n").encode())
            self.wfile.flush()
            while True:
                ready, _, _ = select.select([sock], [], [], 15)
                if ready:
                    if not sock.recv(1024):   # a aba fechou a conexão
                        break
                else:                         # mantém a conexão viva
                    self.wfile.write(b": ok\n\n")
                    self.wfile.flush()
        except (OSError, ValueError):
            pass
        finally:
            _tab_closed()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path.lower().startswith("/dados"):  # os dados só saem pela API
            return self._json({"error": "não encontrado"}, 404)
        if not u.path.startswith("/api/"):
            return super().do_GET()
        if not self._trusted():
            return self._json({"error": "origem não permitida"}, 403)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        parts = [urllib.parse.unquote(x) for x in u.path.split("/")[3:]]
        try:
            if u.path == "/api/alive":
                return self._alive()
            if u.path == "/api/ping":
                return self._json({"ok": True, "background": BACKGROUND})
            if u.path == "/api/db/info":
                return self._json({"path": DATA, "songs": len(load("songs")), "words": len(load("words")),
                                   "history": len(load("history")), "media": len(load_media_index()),
                                   "mediaBytes": folder_size(MEDIA) if os.path.isdir(MEDIA) else 0})
            if u.path.startswith("/api/db/"):
                store = parts[0] if parts else ""
                if store not in STORES:
                    return self._json({"error": "store inválido"}, 400)
                data = load(store)
                if len(parts) == 1:
                    return self._json(list(data.values()))
                rec = data.get(parts[1])
                return self._json(rec) if rec is not None else self._json({"error": "não encontrado"}, 404)
            if u.path.startswith("/api/blob/"):
                meta = load_media_index().get(parts[0] if parts else "")
                path = os.path.join(MEDIA, meta["file"]) if meta else None
                if not path or not os.path.exists(path):
                    return self._json({"error": "arquivo não encontrado"}, 404)
                self.send_response(200)
                self.send_header("Content-Type", meta.get("type") or "application/octet-stream")
                self.send_header("Content-Length", str(os.path.getsize(path)))
                self.end_headers()
                with open(path, "rb") as f:
                    shutil.copyfileobj(f, self.wfile, 1024 * 256)
                return
            if u.path == "/api/playlist":
                lid = q.get("list", "")
                if not re.fullmatch(r"[\w-]{10,64}", lid):
                    return self._json({"error": "id de playlist inválido"}, 400)
                return self._json(yt_playlist(lid))
            if u.path == "/api/oembed":
                vid = q.get("id", "")
                if not re.fullmatch(r"[\w-]{11}", vid):
                    return self._json({"error": "id de vídeo inválido"}, 400)
                return self._json(yt_oembed(vid))
            if u.path == "/api/captions":
                vid = q.get("id", "")
                if not re.fullmatch(r"[\w-]{11}", vid):
                    return self._json({"error": "id de vídeo inválido"}, 400)
                return self._json(yt_captions(vid, q.get("lang", "en"), q.get("force") == "1"))
            if u.path == "/api/itunes":
                return self._json(itunes(q.get("term", "")[:200], q.get("country", "BR")[:2]))
            return self._json({"error": "rota desconhecida"}, 404)
        except Exception as e:  # rede, YouTube mudou o HTML, vídeo indisponível…
            return self._json({"error": f"{type(e).__name__}: {e}"}, 502)


def _route_write(self, method):
    u = urllib.parse.urlparse(self.path)
    if not self._trusted():
        return self._json({"error": "origem não permitida"}, 403)
    parts = [urllib.parse.unquote(x) for x in u.path.split("/")[3:]]
    try:
        if u.path == "/api/bye" and method == "POST":  # usado por versões antigas do index.html
            return self._json({"ok": True})
        if u.path == "/api/shutdown" and method == "POST":
            self._json({"ok": True})
            _shutdown("pedido pelo app")
            return
        if u.path == "/api/open-data" and method == "POST":
            open_folder(DATA)
            return self._json({"ok": True})
        if u.path.startswith("/api/db/"):
            store = parts[0] if parts else ""
            if store not in STORES:
                return self._json({"error": "store inválido"}, 400)
            with LOCK:
                data = load(store)
                if method == "PUT":
                    rec = json.loads(self._body().decode("utf-8"))
                    key = rec.get(KEYS.get(store, "id")) if isinstance(rec, dict) else None
                    if key is None or (len(parts) > 1 and parts[1] != str(key)):
                        return self._json({"error": "registro sem chave"}, 400)
                    data[str(key)] = rec
                elif method == "DELETE" and len(parts) > 1:
                    data.pop(parts[1], None)
                elif method == "DELETE":
                    data.clear()
                else:
                    return self._json({"error": "método inválido"}, 405)
                save(store)
            return self._json({"ok": True})
        if u.path.startswith("/api/blob"):
            bid = parts[0] if parts else ""
            with LOCK:
                idx = load_media_index()
                if method == "DELETE" and not bid:  # apagar todas as mídias
                    shutil.rmtree(MEDIA, ignore_errors=True)
                    _cache["_media"] = {}
                    return self._json({"ok": True})
                if not re.fullmatch(r"[\w-]{1,64}", bid):
                    return self._json({"error": "id inválido"}, 400)
                if method == "DELETE":
                    meta = idx.pop(bid, None)
                    if meta:
                        try:
                            os.remove(os.path.join(MEDIA, meta["file"]))
                        except OSError:
                            pass
                    save_media_index()
                    return self._json({"ok": True})
                if method == "PUT":
                    name = urllib.parse.unquote(self.headers.get("X-File-Name") or "")
                    ext = os.path.splitext(name)[1].lower()
                    if not re.fullmatch(r"\.[a-z0-9]{1,5}", ext or ""):
                        ext = ".bin"
                    os.makedirs(MEDIA, exist_ok=True)
                    old = idx.get(bid)
                    fname = bid + ext
                    n = int(self.headers.get("Content-Length") or 0)
                    tmp = os.path.join(MEDIA, fname + ".tmp")
                    with open(tmp, "wb") as f:
                        left = n
                        while left > 0:
                            chunk = self.rfile.read(min(left, 1024 * 256))
                            if not chunk:
                                break
                            f.write(chunk)
                            left -= len(chunk)
                    _replace(tmp, os.path.join(MEDIA, fname))
                    if old and old.get("file") != fname:
                        try:
                            os.remove(os.path.join(MEDIA, old["file"]))
                        except OSError:
                            pass
                    idx[bid] = {"file": fname, "type": self.headers.get("Content-Type") or "", "name": name, "size": n}
                    save_media_index()
                    return self._json({"ok": True})
        return self._json({"error": "rota desconhecida"}, 404)
    except Exception as e:
        import traceback
        traceback.print_exc()  # aparece na janela preta do servidor
        return self._json({"error": f"{type(e).__name__}: {e}"}, 500)


Handler.do_PUT = lambda self: _route_write(self, "PUT")
Handler.do_DELETE = lambda self: _route_write(self, "DELETE")
Handler.do_POST = lambda self: _route_write(self, "POST")


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    global _httpd
    _setup_log()
    url = f"http://localhost:{PORT}/"
    try:
        _httpd = Server(("127.0.0.1", PORT), Handler)
    except OSError:
        # já tem um servidor rodando: só abre o app no navegador
        log(f"A porta {PORT} já está em uso — o app já está aberto; abrindo o navegador.")
        webbrowser.open(url)
        return
    log(f"Treino de Letras rodando em {url}")
    log(f"Seus dados ficam em: {DATA}")
    try:
        import yt_dlp  # noqa
        log("yt-dlp: instalado (usado para ler as legendas do YouTube)")
    except ImportError:
        log("yt-dlp: NÃO instalado — menos vídeos vão conseguir alinhar pelas legendas")
    if BACKGROUND:
        log("Rodando sem janela. Ele fecha sozinho quando você fecha a aba do app.")
        threading.Thread(target=_watchdog, daemon=True).start()
    else:
        log("Deixe esta janela aberta enquanto usa. Ctrl+C para sair.")
    threading.Thread(target=_update_ytdlp, daemon=True).start()
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        _httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _httpd.server_close()


if __name__ == "__main__":
    main()
