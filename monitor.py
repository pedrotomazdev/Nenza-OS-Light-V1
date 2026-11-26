from time import sleep_ms, ticks_add, ticks_diff, ticks_ms
from config import AMOSTRAS, ATUALIZACAO_MS, DIAGNOSTICO_MEMORIA
from http_json import consultar_api, ler_cabecalho

if DIAGNOSTICO_MEMORIA:
    from diagnostico import medir_memoria


estado = ("CONECTANDO", None)
acao_pc = (None, "")
historico_clima = ("CONECTANDO", ())

def amostra_graficos(api):
    def numero(valor):
        try:
            valor = float(str(valor).strip().rstrip("%").rstrip("Cc").rstrip("\u00b0"))
        except (TypeError, ValueError, OverflowError):
            return None
        return valor if -1e9 <= valor <= 1e9 else None

    return (
        numero((api.get("latency") or {}).get("networkPingMs")),
        numero((api.get("cpu") or {}).get("temperature")),
        numero((api.get("memory") or {}).get("usagePercent")),
    )

def processar_acao_pc(wifi, host, token):
    global acao_pc

    comando, _ = acao_pc
    if comando is None:
        return

    import socket

    resultado = "SEM CONFIG PC"
    if host and token:
        resultado = "SEM WIFI"
        if wifi.isconnected():
            try:
                endereco = socket.getaddrinfo(host, 8085)[0][-1]
                requisicao = (
                    "POST /nenzabuddy/commands/{} HTTP/1.0\r\nHost: {}:8085\r\n"
                    "Authorization: Bearer {}\r\nContent-Length: 0\r\n"
                    "Connection: close\r\n\r\n"
                ).format(comando, host, token).encode()
                resposta = consultar_api(endereco, requisicao)
                print("Ultimate Nenza:", resposta.get("message", "OK"))
                resultado = "COMANDO OK"
            except (OSError, ValueError, TypeError, AttributeError, MemoryError) as erro:
                print("Ultimate Nenza:", erro)
                resultado = "FALHA NO COMANDO"
    acao_pc = (None, resultado)


def enviar_clima(endereco, host_porta, token, leitura):
    import json

    sample_id, temperatura, pressao = leitura
    corpo = json.dumps({
        "sample_id": sample_id,
        "temperature_c": temperatura,
        "pressure_hpa": pressao,
    }).encode()
    cabecalho = (
        "POST /api/meteorologia/leituras HTTP/1.0\r\nHost: {}\r\n"
        "Authorization: Bearer {}\r\nContent-Type: application/json\r\n"
        "Content-Length: {}\r\nConnection: close\r\n\r\n"
    ).format(host_porta, token, len(corpo)).encode()
    consultar_api(endereco, cabecalho + corpo)


def ler_historico_clima(endereco, host_porta):
    import json
    import socket

    requisicao = (
        "GET /api/meteorologia/historico?periodo=24h HTTP/1.0\r\nHost: {}\r\n"
        "Connection: close\r\n\r\n"
    ).format(host_porta).encode()
    pontos = [None] * AMOSTRAS
    total = 0
    buffer = b""
    em_buckets = False
    chave = b'"buckets"'
    conexao = socket.socket()
    try:
        conexao.settimeout(3)
        conexao.connect(endereco)
        restante, em_blocos = ler_cabecalho(conexao, requisicao)
        if em_blocos or restante is None or not 0 < restante <= 512_000:
            raise ValueError("Tamanho do historico invalido")
        while restante:
            bloco = conexao.read(min(1024, restante))
            if not bloco:
                break
            restante -= len(bloco)
            buffer += bloco
            if not em_buckets:
                posicao = buffer.find(chave)
                if posicao < 0:
                    buffer = buffer[-(len(chave) - 1):]
                    continue
                inicio = buffer.find(b"[", posicao + len(chave))
                if inicio < 0:
                    buffer = buffer[posicao:]
                    if len(buffer) > 1024:
                        raise ValueError("Lista do historico invalida")
                    continue
                buffer = buffer[inicio + 1:]
                em_buckets = True

            # A API envia buckets planos e em ordem cronologica.
            buffer = buffer.lstrip(b" \r\n\t,")
            while buffer.startswith(b"{"):
                fim = buffer.find(b"}")
                if fim < 0:
                    break
                bucket = json.loads(buffer[:fim + 1])
                temperatura = float(bucket["temperature_c"])
                pressao = float(bucket["pressure_hpa"])
                if -40 <= temperatura <= 85 and 300 <= pressao <= 1100:
                    pontos[total % AMOSTRAS] = (temperatura, pressao)
                    total += 1
                buffer = buffer[fim + 1:].lstrip(b" \r\n\t,")
            if buffer.startswith(b"]"):
                primeiro = max(0, total - AMOSTRAS)
                return tuple(pontos[indice % AMOSTRAS] for indice in range(primeiro, total))
            if len(buffer) > 1024 or (buffer and not buffer.startswith(b"{")):
                raise ValueError("Bucket do historico invalido")
    finally:
        conexao.close()
    raise ValueError("Historico incompleto")


def monitorar_servidor(clima):
    global estado, historico_clima

    import network
    import socket
    from binascii import hexlify
    from os import urandom
    from rede_config import carregar

    weather_port = 8084
    try:
        import secrets
        weather_token = getattr(secrets, "WEATHER_TOKEN", "")
        weather_port = getattr(secrets, "WEATHER_PORT", weather_port)
    except ImportError:
        weather_token = ""

    ssid, senha, api_url, host_pc, token = carregar()
    host_porta, rota = api_url[len("http://"):].split("/", 1)
    host, _, porta = host_porta.partition(":")
    requisicao = (
        "GET /{} HTTP/1.0\r\nHost: {}\r\nConnection: close\r\n\r\n"
        .format(rota, host_porta).encode()
    )
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    telas = None
    proxima_sincronizacao = ticks_ms()
    proximo_envio_clima = proxima_sincronizacao
    proximo_historico_clima = proxima_sincronizacao
    leitura_pendente = None

    while True:
        try:
            if not wifi.isconnected():
                estado = ("SEM WIFI" if telas else "CONECTANDO", telas)
                wifi.connect(ssid, senha)
                inicio = ticks_ms()
                while not wifi.isconnected() and ticks_diff(ticks_ms(), inicio) < 12_000:
                    sleep_ms(250)
                if not wifi.isconnected():
                    wifi.disconnect()
                    raise OSError("Wi-Fi indisponivel")
                if DIAGNOSTICO_MEMORIA:
                    medir_memoria("Wi-Fi conectado")

            endereco = socket.getaddrinfo(host, int(porta or "80"))[0][-1]
            estado, amostra = ler_snapshot(endereco, requisicao)
            telas = estado[1]
            if DIAGNOSTICO_MEMORIA:
                medir_memoria("API local")
        except (OSError, ValueError, TypeError, AttributeError, MemoryError) as erro:
            estado = ("API FALHOU" if wifi.isconnected() else "SEM WIFI", telas)
            print("[NENZAHUB]", erro)
            amostra = (None, None, None)

        registrar_amostra(amostra)
        if weather_token and wifi.isconnected() and ticks_diff(ticks_ms(), proximo_envio_clima) >= 0:
            try:
                if leitura_pendente is None:
                    # A tupla atual e publicada inteira pelo loop do sensor.
                    temperatura, pressao = clima.atual
                    if temperatura is not None and pressao is not None and (
                        -40 <= temperatura <= 85 and 300 <= pressao <= 1100
                    ):
                        leitura_pendente = (hexlify(urandom(16)).decode(), temperatura, pressao)
                if leitura_pendente is not None:
                    destino = socket.getaddrinfo(host, weather_port)[0][-1]
                    enviar_clima(destino, "{}:{}".format(host, weather_port), weather_token, leitura_pendente)
                    leitura_pendente = None
                    proximo_envio_clima = ticks_add(ticks_ms(), 60_000)
            except (OSError, ValueError, TypeError, MemoryError) as erro:
                print("[METEOROLOGIA]", erro)

        if wifi.isconnected() and ticks_diff(ticks_ms(), proximo_historico_clima) >= 0:
            try:
                destino = socket.getaddrinfo(host, weather_port)[0][-1]
                pontos = ler_historico_clima(destino, "{}:{}".format(host, weather_port))
                historico_clima = ("LIVE", pontos)
            except (OSError, ValueError, TypeError, KeyError, MemoryError) as erro:
                historico_clima = ("SEM HIST", historico_clima[1])
                print("[METEOROLOGIA] Historico:", erro)
            proximo_historico_clima = ticks_add(ticks_ms(), 60_000)

        if (
            proxima_sincronizacao is not None and wifi.isconnected()
            and ticks_diff(ticks_ms(), proxima_sincronizacao) >= 0
        ):
            try:
                import ntptime
                ntptime.settime()
            except ImportError:
                proxima_sincronizacao = None
                print("[RELOGIO] Modulo ntptime indisponivel")
            except (OSError, ValueError, OverflowError, MemoryError) as erro:
                proxima_sincronizacao = ticks_add(ticks_ms(), 60_000)
                print("[RELOGIO] Falha NTP:", erro)
            else:
                proxima_sincronizacao = ticks_add(ticks_ms(), 3_600_000)
        prazo = ticks_add(ticks_ms(), ATUALIZACAO_MS)
        while ticks_diff(prazo, ticks_ms()) > 0:
            processar_acao_pc(wifi, host_pc, token)
            sleep_ms(50)


def atualizar_servidor(clima):
    global estado

    try:
        monitorar_servidor(clima)
    except Exception as erro:
        estado = ("ERRO REDE", estado[1])
        print("Monitor:", erro)

def medida(valor, unidade=""):
    if valor is None or valor == "":
        return "--"
    return str(valor).replace("\u00b0", "") + unidade


def duracao(segundos):
    if segundos is None:
        return "--"
    minutos = int(segundos) // 60
    return "{}d {:02d}h {:02d}m".format(minutos // 1440, minutos // 60 % 24, minutos % 60)


def barra(valor):
    try:
        return max(0, min(100, float(str(valor).rstrip("%"))))
    except (ValueError, TypeError):
        return None


def preparar_telas(api):
    status = api.get("status")
    if not isinstance(status, str):
        raise ValueError("Resposta sem status")
    latencia = api.get("latency") or {}
    uptime = api.get("uptime") or {}
    memoria = api.get("memory") or {}
    cpu = api.get("cpu") or {}
    termica = api.get("thermal") or {}
    wifi = api.get("wifi") or {}
    android = api.get("android") or {}
    bateria = android.get("battery") or {}
    disco = android.get("disk") or {}
    ram_pct = memoria.get("usagePercent")
    sinal = wifi.get("signalPercent")
    carga = bateria.get("percentage")
    disco_pct = disco.get("usagePercent")
    tomada = bateria.get("plugged")
    tomada_texto = "--"
    if tomada is not None:
        tomada_texto = "NAO" if tomada == "UNPLUGGED" else "SIM"

    return (
        (("Status: " + status.upper(), "Ping: " + medida(latencia.get("networkPingMs"), " ms"),
          "Up: " + duracao(uptime.get("systemSeconds"))), None),
        (("Nucleos: " + medida(cpu.get("cores")), "CPU: " + medida(cpu.get("temperature")),
          "Media: " + medida(termica.get("averageTemp"), "C")), None),
        (("Uso: " + medida(ram_pct, "%"), "Usada: " + medida(memoria.get("usedMB"), " MB"),
          "Total: " + medida(memoria.get("totalMB"), " MB")), barra(ram_pct)),
        ((medida(wifi.get("ip")), "Sinal: " + medida(sinal, "%"),
          "Link: " + medida(wifi.get("linkSpeedMbps"), " Mbps")), barra(sinal)),
        (("Carga: " + medida(carga, "%"), "Temp: " + medida(bateria.get("temperature"), "C"),
          "Tomada: " + tomada_texto), barra(carga)),
        (("Uso: " + medida(disco_pct), "Usado: " + medida(disco.get("used")),
          "Livre: " + medida(disco.get("available"))), barra(disco_pct)),
    )

historico = [None] * AMOSTRAS
revisao_historico = 0
trava_historico = None


def registrar_amostra(amostra):
    global revisao_historico

    with trava_historico:
        historico[revisao_historico % AMOSTRAS] = amostra
        revisao_historico += 1


def copiar_metrica(metrica, destino):
    if trava_historico is None:
        return 0, 0
    # A trava protege a copia da serie, sem abranger operacoes no OLED.
    with trava_historico:
        revisao = revisao_historico
        quantidade = min(revisao, AMOSTRAS)
        primeiro = revisao - quantidade
        for indice in range(quantidade):
            destino[indice] = historico[(primeiro + indice) % AMOSTRAS][metrica]
    return revisao, quantidade


def ultima_amostra():
    if trava_historico is not None:
        with trava_historico:
            if revisao_historico:
                return revisao_historico, historico[(revisao_historico - 1) % AMOSTRAS]
    return 0, (None, None, None)


def ler_snapshot(endereco, requisicao):
    api = consultar_api(endereco, requisicao)
    telas = preparar_telas(api)
    conexao = "LIVE" if api["status"].lower() == "ok" else "ALERTA"
    return (conexao, telas), amostra_graficos(api)
