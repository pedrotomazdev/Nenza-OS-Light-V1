from time import gmtime
from animacoes import DIGITOS_RELOGIO, desenhar_logo_nenza
from clima import BLOCOS_24H, PRESSAO, TEMPERATURA, altitude_estimada, indicador_experimental
from config import (
    ANIMACOES, GRAFICOS, AMOSTRAS,
    POMODORO_MS, PRESSAO_NIVEL_MAR_HPA,
)

# Cada entrada possui um titulo e o destino. Numeros abrem telas da API.
MENU = (
    ("ULTIMATE NENZA", "abrir"),
    ("STATUS NENZAHUB", 0),
    ("CPU", 1),
    ("MEMORIA", 2),
    ("REDE", 3),
    ("BATERIA", 4),
    ("DISCO", 5),
    ("ABRIR CHROME", "chrome"),
    ("ABRIR NENZAHUB", "nenzahub"),
    ("NENZAHOME", "nenzahome"),
    ("NENZALAB", "nenzalab"),
    ("ABRIR BRAVE", "brave"),
    ("ABRIR DISCORD", "discord"),
    ("MODO TRABALHO", "pc"),
    ("CONFIGURACOES", "config"),
    ("GRAFICOS", "graficos"),
    ("TELA INICIAL", "painel"),
    ("CLIMA", "clima"),
)
ACOES_FAVORITAS = tuple(
    i for i, (_, destino) in enumerate(MENU)
    if isinstance(destino, str) and destino not in ("pc", "config", "graficos", "painel", "clima")
)

# Sprites de 8x8, ampliados no centro do carrossel.
# Cada byte e uma linha, com o bit mais alto a esquerda.
ICONES_MENU = {
    "abrir": b"\x10\x38\x7c\xfe\x7c\x38\x10\x01",
    0: b"\x00\x08\x08\x14\xe7\x20\x20\x00",  # activity
    1: b"\x24\x7e\x42\xdb\xdb\x42\x7e\x24",  # cpu
    2: b"\x00\x7e\x42\x5a\x42\x7e\x24\x00",  # memory-stick
    3: b"\x00\x3c\x42\x00\x18\x24\x00\x18",  # wifi
    4: b"\x00\x00\x7e\x4b\x4b\x7e\x00\x00",  # battery
    5: b"\x00\x3c\x42\x81\xff\x85\xff\x00",  # hard-drive
    "chrome": b"\x3c\x7e\xc3\x9f\xb9\xe3\x7e\x3c",
    "nenzahub": b"\x66\xff\xff\x66\x66\xff\xff\x66",
    "nenzahome": b"\x18\x24\x42\xff\x42\x5a\x5a\x7e",  # house
    "nenzalab": b"\x3c\x18\x18\x24\x24\x5a\x42\x3c",  # flask-conical
    "brave": b"\x42\xff\xa5\x99\xa5\x5a\x24\x18",
    "discord": b"\x00\x24\x7e\xff\xdb\xff\x42\x00",
    "graficos": b"\x00\x02\x05\x08\x50\xa0\x00\x7e",
    "pc": b"\x18\x24\x7e\x42\x7e\x42\x7e\x00",  # briefcase-business
    "config": b"\x22\x22\xfa\x22\x44\x5f\x44\x44",
    "animacao": b"\x00\xff\x81\x99\x91\x81\xff\x00",  # monitor-play
    "voltar": b"\x00\x10\x20\x7e\x20\x10\x00\x00",  # arrow-left
    "wifi": b"\x00\x7e\x81\x3c\x42\x18\x00\x18",
    "painel": b"\x10\x28\x44\x82\x44\x54\x54\x7c",  # house
    "clima": b"\x30\x48\x78\x1c\x22\x41\x7e\x00",
}

# Adaptacoes para OLED de clock, calendar-days, battery, thermometer e activity.
ICONE_TEMPERATURA = b"\x18\x24\x24\x34\x34\x42\x5a\x3c"
ICONE_PING = b"\x00\x10\x18\x28\xe7\x14\x0c\x08"
GLIFOS_PAINEL = dict(zip("0123456789-:", DIGITOS_RELOGIO))
GLIFOS_PAINEL.update({
    ".": (0, 0, 0, 0, 2), "%": (4, 1, 2, 4, 1),
    "+": (0, 2, 7, 2, 0), "C": (7, 4, 4, 4, 7),
    "m": (0, 0, 7, 7, 5), "s": (0, 0, 7, 6, 3),
    "°": (6, 6, 0, 0, 0),
    "h": (4, 4, 6, 5, 5), "P": (6, 5, 6, 4, 4),
    "a": (0, 0, 3, 5, 7), " ": (0, 0, 0, 0, 0),
    "/": (1, 1, 2, 4, 4),
})


def desenhar_icone(oled, icone, x, y, cor, tamanho=8):
    for dy, bits in enumerate(icone):
        for dx in range(8):
            if bits & (0x80 >> dx):
                if tamanho == 8:
                    oled.pixel(x + dx, y + dy, cor)
                else:
                    px = dx * tamanho // 8
                    py = dy * tamanho // 8
                    oled.fill_rect(x + px, y + py, (dx + 1) * tamanho // 8 - px,
                                   (dy + 1) * tamanho // 8 - py, cor)


def desenhar_texto_pequeno(oled, texto, x, y):
    for caractere in texto:
        for dy, bits in enumerate(GLIFOS_PAINEL[caractere]):
            for dx in range(3):
                if bits & (4 >> dx):
                    oled.pixel(x + dx, y + dy, 1)
        x += 4


def texto_centro(oled, texto, y):
    oled.text(texto[:16], (128 - min(16, len(texto)) * 8) // 2, y)


def digitos_grandes(oled, texto, x, y):
    for caractere in texto:
        for linha, bits in enumerate(GLIFOS_PAINEL[caractere]):
            for coluna in range(3):
                if bits & (4 >> coluna):
                    oled.fill_rect(x + coluna * 3, y + linha * 3, 3, 3, 1)
        x += 12


def capsula(oled, x, y, largura):
    if largura >= 4:
        oled.hline(x + 1, y, largura - 2, 1)
        oled.fill_rect(x, y + 1, largura, 2, 1)
        oled.hline(x + 1, y + 3, largura - 2, 1)
    elif largura:
        oled.fill_rect(x, y + 1, largura, 2, 1)


def desenhar_painel(oled, amostra, utc, clima, bateria, conexao, relevo=0):
    ping = amostra[0]
    temperatura, pressao = clima
    ano, mes, dia, hora, minuto, *_ = gmtime(max(0, utc - 3 * 3600))
    horario = "{:02d}:{:02d}".format(hora, minuto) if ano >= 2025 else "--:--"
    data = "{:02d}/{:02d}".format(dia, mes) if ano >= 2025 else "--/--"
    bateria_texto = "--%" if bateria is None else "{:.0f}%".format(bateria)
    ping_texto = "--ms" if ping is None or ping < 0 else "{:.0f}ms".format(ping)
    if len(ping_texto) > 6:
        ping_texto = "999+ms"
    oled.fill(0)
    desenhar_icone(oled, ICONES_MENU[4], 3, 3, 1)
    desenhar_texto_pequeno(oled, bateria_texto, 14, 4)
    if conexao in ("LIVE", "ALERTA", "API FALHOU"):
        desenhar_icone(oled, ICONES_MENU[3], 61, 2, 1)
        if conexao != "LIVE":
            oled.pixel(71, 3, 1)
    else:
        oled.hline(62, 6, 5, 1)
    x_ping = 125 - 4 * len(ping_texto)
    desenhar_icone(oled, ICONE_PING, x_ping - 10, 2, 1)
    desenhar_texto_pequeno(oled, ping_texto, x_ping, 4)
    digitos_grandes(oled, horario, 21, 19)
    desenhar_texto_pequeno(oled, data, 92, 25)
    desenhar_logo_nenza(oled, 43, 39 - relevo)
    temp_texto = "-- C" if temperatura is None else "{:.1f} C".format(temperatura)
    pressao_texto = "-- hPa" if pressao is None else "{:.1f} hPa".format(pressao)
    desenhar_icone(oled, ICONE_TEMPERATURA, 4, 54, 1)
    desenhar_texto_pequeno(oled, temp_texto, 15, 56)
    x_pressao = 125 - 4 * len(pressao_texto)
    desenhar_icone(oled, ICONES_MENU["clima"], x_pressao - 11, 54, 1)
    desenhar_texto_pequeno(oled, pressao_texto, x_pressao, 56)


ROTULOS_MENU = (
    "Ultimate Nenza", "Status NenzaHub", "CPU", "Memoria", "Rede", "Bateria",
    "Disco", "Abrir Chrome", "Abrir NenzaHub", "NenzaHome", "NenzaLab",
    "Abrir Brave", "Abrir Discord", "Modo foco", "Ajustes", "Graficos",
    "Tela inicial", "Clima",
)
ROTULOS_CONFIG = ("Animacao", "Configurar Wi-Fi", "Voltar")
ROTULOS_MONITOR = ("NenzaHub", "CPU", "Memoria", "Rede", "Bateria", "Disco")
PASSO_CARROSSEL = 43


def desenhar_menu(oled, selecionado, rodape, posicao, confirmacao, ajustes=False):
    itens = CONFIG_ITENS if ajustes else MENU
    rotulos = ROTULOS_CONFIG if ajustes else ROTULOS_MENU
    total = len(itens)
    oled.fill(0)
    oled.text(rotulos[selecionado], 4, 3)
    centro = int(posicao)
    primeiro = (centro - 64) // PASSO_CARROSSEL
    for virtual in range(primeiro, primeiro + 5):
        indice = virtual % total
        # No menu de tres itens cada icone aparece uma vez.
        deslocamento = virtual * PASSO_CARROSSEL - centro
        if abs(deslocamento) * 2 > total * PASSO_CARROSSEL:
            continue
        x = 64 + deslocamento
        selecionado_visual = abs(deslocamento) < PASSO_CARROSSEL // 2
        raio = 12 - min(5, abs(deslocamento) // 4)
        y = 31 + (12 - raio) // 2
        oled.ellipse(x, y, raio, raio, 1, selecionado_visual)
        tamanho = 8 + max(0, 8 - abs(deslocamento) // 3)
        desenhar_icone(oled, ICONES_MENU[itens[indice][1]], x - tamanho // 2,
                       y - tamanho // 2, 0 if selecionado_visual else 1, tamanho)

    for indice in range(total):
        x = 64 - (total - 1) * 2 + indice * 4
        largura = 3 if indice == selecionado else 1
        oled.hline(x - largura // 2, 48, largura, 1)
    oled.text(rodape[:1].upper() + rodape[1:10].lower(), 3, 56)
    oled.text(confirmacao, 125 - len(confirmacao) * 8, 56)


CONFIG_ITENS = (("ANIMACAO", "animacao"), ("CONFIGURAR WIFI", "wifi"), ("VOLTAR", "voltar"))
CONFIG_WIFI = 1
CONFIG_VOLTAR = 2


def desenhar_cabecalho(oled, titulo):
    oled.text(titulo[:16], 3, 4)


TITULOS_CLIMA = (
    "Tend. pressao", "Altitude est.", "Taxa termica",
    "Temp 24h (C)", "Pressao 24h", "Tempo exp.",
)
PAGINA_ALTITUDE = 1


def desenhar_tendencia(oled, x, y, delta):
    if delta is None:
        return
    if delta == 0:
        oled.hline(x, y + 3, 7, 1)
    elif delta > 0:
        oled.line(x, y + 6, x + 6, y, 1)
        oled.hline(x + 2, y, 5, 1)
        oled.vline(x + 6, y, 5, 1)
    else:
        oled.line(x, y, x + 6, y + 6, 1)
        oled.hline(x + 2, y + 6, 5, 1)
        oled.vline(x + 6, y + 2, 5, 1)


def desenhar_clima(oled, pagina, resumo, pressao, volta):
    oled.fill(0)
    desenhar_cabecalho(oled, TITULOS_CLIMA[pagina])
    desenhar_icone(oled, ICONES_MENU["clima"], 116, 4, 1)
    if pagina == 0:
        for linha, horas in enumerate((1, 3)):
            delta = resumo.variacao(PRESSAO, horas)
            valor = "--" if delta is None else "{:+.1f} hPa".format(delta)
            y = 20 + 13 * linha
            oled.text("{}h {}".format(horas, valor), 4, y)
            desenhar_tendencia(oled, 116, y, delta)
    elif pagina == PAGINA_ALTITUDE:
        altitude = altitude_estimada(pressao)
        valor = "Sem leitura" if altitude is None else "{:.0f} m".format(altitude)
        oled.text(valor, 0, 20)
        oled.text("Ref {:.2f} hPa".format(PRESSAO_NIVEL_MAR_HPA), 0, 33)
    elif pagina == 2:
        taxa = resumo.variacao(TEMPERATURA, 1)
        if taxa is None:
            oled.text("Aguardando 1h", 0, 20)
        else:
            oled.text("{:+.1f} C/h".format(taxa), 0, 20)
            sentido = "Aquecendo" if taxa >= 0.05 else "Esfriando" if taxa <= -0.05 else "Estavel"
            oled.text(sentido, 4, 33)
            desenhar_tendencia(oled, 116, 20, taxa if abs(taxa) >= 0.05 else 0)
    elif pagina in (3, 4):
        estatisticas = resumo.estatisticas(TEMPERATURA if pagina == 3 else PRESSAO)
        if estatisticas is None:
            oled.text("Aguardando dados", 0, 20)
        else:
            minima, maxima, media, cobertura = estatisticas
            oled.text("{:.1f} a {:.1f}".format(minima, maxima), 0, 17)
            oled.text("Med {:.1f}".format(media), 0, 26)
            oled.text("Amp {:.1f}".format(maxima - minima), 0, 35)
            oled.text("Blocos {:3}/{}".format(cobertura, BLOCOS_24H), 0, 44)
    else:
        sinal = indicador_experimental(resumo.variacao(PRESSAO, 3), resumo.variacao(TEMPERATURA, 1))
        oled.text(sinal, 0, 20)
        oled.text("Sem previsao", 0, 33)
    oled.text("1:< 2:>", 3, 56)
    oled.text(volta + " Menu", 125 - (len(volta) + 5) * 8, 56)


def desenhar_config(oled, animacao, confirmacao):
    oled.fill(0)
    desenhar_cabecalho(oled, "Descanso")
    desenhar_icone(oled, ICONES_MENU["animacao"], 60, 17, 1)
    texto_centro(oled, ANIMACOES[animacao], 34)
    oled.text("1:< 2:>", 3, 56)
    oled.text(confirmacao, 125 - len(confirmacao) * 8, 56)


def desenhar_foco(oled, segundos, volta):
    oled.fill(0)
    desenhar_cabecalho(oled, "Modo foco")
    if segundos:
        digitos_grandes(oled, "{:02d}:{:02d}".format(segundos // 60, segundos % 60), 35, 22)
        largura = 112 * segundos // (POMODORO_MS // 1000)
        oled.hline(8, 45, 112, 1)
        capsula(oled, 8, 44, largura)
        oled.text(volta + " Cancelar", 3, 56)
    else:
        texto_centro(oled, "Sessao completa", 24)
        oled.text(volta + " Voltar", 3, 56)


def desenhar_grafico(oled, metrica, valores, quantidade, conexao, volta):
    unidade = GRAFICOS[metrica][1]
    atual = valores[quantidade - 1] if quantidade else None
    oled.fill(0)
    valor = "--" if atual is None else "{:.1f}{}".format(atual, unidade)
    nome = ("Ping", "CPU", "RAM", "Temp", "Press")[metrica]
    desenhar_cabecalho(oled, nome)
    if len(valor) > 9:
        valor = "{:.2g}{}".format(atual, unidade)
    oled.text(valor[:10], 124 - min(10, len(valor)) * 8, 4)
    minimo = maximo = None
    for indice in range(quantidade):
        valor = valores[indice]
        if valor is not None:
            if minimo is None or valor < minimo:
                minimo = valor
            if maximo is None or valor > maximo:
                maximo = valor
    if minimo is not None:
        for y in (18, 34, 50):
            for x in range(5, 125, 6):
                oled.pixel(x, y, 1)
        anterior_x = None
        for indice in range(quantidade):
            valor = valores[indice]
            if valor is None:
                anterior_x = None
                continue
            x = 5 + (AMOSTRAS - quantidade + indice) * 2
            y = 34
            if maximo > minimo:
                y = 51 - int(34 * (valor - minimo) / (maximo - minimo))
            if anterior_x is None:
                oled.pixel(x, y, 1)
            else:
                oled.line(anterior_x, anterior_y, x, y, 1)
            anterior_x, anterior_y = x, y
        if atual is not None and quantidade > 1 and valores[quantidade - 2] is not None:
            desenhar_tendencia(oled, 126 - 7, 56, atual - valores[quantidade - 2])
    else:
        oled.text("Aguardando dados", 0, 28)
    oled.text("1:< 2:>" if conexao in (None, "LIVE") else conexao[:7], 0, 56)
    oled.text(volta + " Menu", 115 - (len(volta) + 5) * 8, 56)


def desenhar_acao(oled, selecionado, resultado, volta):
    oled.fill(0)
    desenhar_cabecalho(oled, ROTULOS_MENU[selecionado])
    desenhar_icone(oled, ICONES_MENU[MENU[selecionado][1]], 60, 19, 1)
    texto_centro(oled, resultado, 36)
    oled.text(volta + " Voltar", 3, 56)



def desenhar_tela(oled, tela, snapshot, progresso):
    conexao, telas = snapshot
    oled.fill(0)
    desenhar_icone(oled, ICONES_MENU[tela], 4, 3, 1)
    oled.text(ROTULOS_MONITOR[tela], 17, 3)

    if telas is None:
        oled.text("Aguardando dados", 0, 28)
        oled.text(conexao, 0, 47)
    else:
        linhas, percentual = telas[tela]
        for i, linha in enumerate(linhas):
            oled.text(linha[:16], 0, 16 + i * 11)
        if percentual is not None:
            y_barra = 52 if conexao == "LIVE" else 46
            oled.hline(5, y_barra + 1, 118, 1)
            capsula(oled, 5, y_barra, int(progresso * 118 / 100))
        if conexao in ("SEM WIFI", "API FALHOU", "ERRO REDE"):
            oled.text("Cache " + conexao.lower(), 0, 54)
        elif conexao == "ALERTA":
            oled.text("NENZA / ALERTA", 0, 54)
        elif percentual is None:
            oled.text("Live", 4, 54)
