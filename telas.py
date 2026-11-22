from time import gmtime
from animacoes import desenhar_logo_nenza
from clima import BLOCOS_24H, PRESSAO, TEMPERATURA, altitude_estimada, indicador_experimental
from config import (
    FAIXA_AMARELA_PX, ANIMACOES, GRAFICOS, AMOSTRAS, TITULOS,
    POMODORO_MS, PRESSAO_NIVEL_MAR_HPA,
)

# Cada entrada possui um titulo e o destino. Numeros abrem telas da API.
MENU = (
    ("ULTIMATE NENZA", "abrir"),
    ("HEALTH API", 0),
    ("CPU", 1),
    ("MEMORIA", 2),
    ("REDE", 3),
    ("BATERIA", 4),
    ("DISCO", 5),
    ("ABRIR CHROME", "chrome"),
    ("NENZAHUB", "nenzahub"),
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

# Adaptacoes 8x8 de simbolos Lucide (https://lucide.dev/icons/).
# Cada byte e uma linha, com o bit mais alto a esquerda.
ICONES_MENU = {
    "abrir": b"\x18\x18\x3c\x7e\x7e\x3c\x18\x18",  # sparkles
    0: b"\x00\x08\x08\x14\xe7\x20\x20\x00",  # activity
    1: b"\x24\x7e\x42\xdb\xdb\x42\x7e\x24",  # cpu
    2: b"\x00\x7e\x42\x5a\x42\x7e\x24\x00",  # memory-stick
    3: b"\x00\x3c\x42\x00\x18\x24\x00\x18",  # wifi
    4: b"\x00\x00\x7e\x4b\x4b\x7e\x00\x00",  # battery
    5: b"\x00\x3c\x42\x81\xff\x85\xff\x00",  # hard-drive
    "chrome": b"\x3c\x42\x99\xa5\xa5\x99\x42\x3c",  # globe
    "nenzahub": b"\x00\x77\x55\x77\x00\x77\x55\x77",  # layout-grid
    "nenzahome": b"\x18\x24\x42\xff\x42\x5a\x5a\x7e",  # house
    "nenzalab": b"\x3c\x18\x18\x24\x24\x5a\x42\x3c",  # flask-conical
    "brave": b"\x7e\x42\x42\x42\x42\x24\x18\x00",  # shield
    "discord": b"\x7e\x81\x81\x81\x81\xfe\x40\x20",  # message-square
    "graficos": b"\x80\x80\x86\x89\xb0\xc0\x80\xff",
    "pc": b"\x18\x24\x7e\x42\x7e\x42\x7e\x00",  # briefcase-business
    "config": b"\x18\x5a\x66\xc3\xc3\x66\x5a\x18",  # settings
    "animacao": b"\x00\xff\x81\x99\x91\x81\xff\x00",  # monitor-play
    "voltar": b"\x00\x10\x20\x7e\x20\x10\x00\x00",  # arrow-left
    "wifi": b"\x00\x7e\x81\x3c\x42\x18\x00\x18",
    "painel": b"\x10\x28\x44\x82\x44\x54\x54\x7c",  # house
    "clima": b"\x00\x30\x48\x4e\x81\x81\x7e\x00",
}

# Adaptacoes 8x8 de memory-stick e activity, do Lucide.
ICONE_RAM = b"\x00\x00\xff\x91\xbd\xff\x54\x00"
ICONE_PING = b"\x00\x10\x18\x28\xe7\x14\x0c\x08"


def desenhar_icone(oled, icone, x, y, cor):
    for dy, bits in enumerate(icone):
        for dx in range(8):
            if bits & (0x80 >> dx):
                oled.pixel(x + dx, y + dy, cor)


def desenhar_relogio(oled, utc):
    ano, mes, dia, hora, minuto, *_ = gmtime(max(0, utc - 3 * 3600))
    if ano < 2025:
        data, horario = "--/--/----", "--:--"
    else:
        data = "{:02d}/{:02d}/{:04d}".format(dia, mes, ano)
        horario = "{:02d}:{:02d}".format(hora, minuto)
    oled.text(horario, 44, 43)
    oled.text(data, 24, 54)


def desenhar_painel(oled, amostra, utc, clima):
    ping, _, ram = amostra
    temperatura, pressao = clima
    ram_texto = "--%" if ram is None or not 0 <= ram <= 100 else "{:.0f}%".format(ram)
    ping_texto = "--ms" if ping is None or ping < 0 else "{:.0f}ms".format(ping)
    if len(ping_texto) > 6:
        ping_texto = ">999ms"
    oled.fill(0)
    desenhar_icone(oled, ICONE_RAM, 0, 0, 1)
    desenhar_icone(oled, ICONE_PING, 120, 0, 1)
    oled.text(ram_texto, 0, 9)
    oled.text(ping_texto, 128 - len(ping_texto) * 8, 9)
    temp_texto = "--C" if temperatura is None else "{:.1f}C".format(temperatura)
    pressao_texto = "--hPa" if pressao is None else "{:.1f}hPa".format(pressao)
    clima_texto = temp_texto + " " + pressao_texto
    oled.text(clima_texto, (128 - len(clima_texto) * 8) // 2, 18)
    desenhar_logo_nenza(oled, 43, 27)
    desenhar_relogio(oled, utc)
    oled.show()


def desenhar_item_menu(oled, item, y, cor):
    titulo, destino = item
    desenhar_icone(oled, ICONES_MENU[destino], 0, y, cor)
    oled.text(titulo[:15], 8, y, cor)


def desenhar_menu(oled, selecionado, rodape, itens=MENU):
    oled.fill(0)
    oled.fill_rect(0, 0, 128, 14, 1)
    desenhar_item_menu(oled, itens[selecionado], 3, 0)
    for linha in range(1, min(4, len(itens))):
        y = 16 + (linha - 1) * 11
        desenhar_item_menu(oled, itens[(selecionado + linha) % len(itens)], y, 1)

    rodape_y = 64 - FAIXA_AMARELA_PX
    oled.rect(0, rodape_y, 128, FAIXA_AMARELA_PX, 1)
    oled.text(rodape[:11], 4, rodape_y + 4)
    oled.text("3:OK", 92, rodape_y + 4)
    oled.show()


CONFIG_ITENS = (("ANIMACAO", "animacao"), ("CONFIGURAR WIFI", "wifi"), ("VOLTAR", "voltar"))
CONFIG_WIFI = 1
CONFIG_VOLTAR = 2


def desenhar_cabecalho(oled, titulo):
    oled.text(titulo, 0, 4)
    oled.hline(0, FAIXA_AMARELA_PX - 2, 128, 1)


TITULOS_CLIMA = (
    "TEND. PRESSAO", "ALTITUDE EST.", "TAXA TERMICA",
    "TEMP 24H (C)", "PRESS 24H (hPa)", "TEMPO EXP.",
)
PAGINA_ALTITUDE = 1


def desenhar_clima(oled, pagina, resumo, pressao):
    oled.fill(0)
    desenhar_cabecalho(oled, TITULOS_CLIMA[pagina])
    if pagina == 0:
        for linha, horas in enumerate((1, 3)):
            delta = resumo.variacao(PRESSAO, horas)
            valor = "--" if delta is None else "{:+.1f} hPa".format(delta)
            oled.text("{}h {}".format(horas, valor), 0, 20 + 13 * linha)
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
            oled.text(sentido, 0, 33)
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
    oled.text("1:< 2:> 3:MENU", 0, 56)
    oled.show()


def desenhar_config(oled, item, editando, animacao):
    if not editando:
        desenhar_menu(oled, item, "1:<  2:>", CONFIG_ITENS)
        return

    oled.fill(0)
    desenhar_cabecalho(oled, "ANIMACAO")
    valor = ANIMACOES[animacao]
    oled.text(valor, (128 - len(valor) * 8) // 2, 23)
    oled.text("1:<  2:>  3:OK", 0, 56)
    oled.show()


def desenhar_foco(oled, segundos):
    oled.fill(0)
    desenhar_cabecalho(oled, "MODO FOCO")
    if segundos:
        oled.text("{:02d}:{:02d}".format(segundos // 60, segundos % 60), 44, 24)
        oled.rect(0, 40, 128, 8, 1)
        largura = 124 * segundos // (POMODORO_MS // 1000)
        if largura:
            oled.fill_rect(2, 42, largura, 4, 1)
        oled.text("3:CANCELAR", 0, 56)
    else:
        oled.text("SESSAO COMPLETA", 0, 24)
        oled.text("3:VOLTAR", 0, 56)
    oled.show()


def desenhar_grafico(oled, metrica, valores, quantidade, conexao):
    nome, unidade = GRAFICOS[metrica]
    atual = valores[quantidade - 1] if quantidade else None
    oled.fill(0)
    valor = "--" if atual is None else "{:.1f}{}".format(atual, unidade)
    desenhar_cabecalho(oled, "{} {}".format(nome, valor)[:16])
    minimo = maximo = None
    for indice in range(quantidade):
        valor = valores[indice]
        if valor is not None:
            if minimo is None or valor < minimo:
                minimo = valor
            if maximo is None or valor > maximo:
                maximo = valor
    if minimo is not None:
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
    else:
        oled.text("Aguardando dados", 0, 28)
    rodape = "1:< 2:> 3:MENU" if conexao in (None, "LIVE") else conexao[:16]
    oled.text(rodape, 0, 56)
    oled.show()

def desenhar_acao(oled, selecionado, resultado):
    oled.fill(0)
    desenhar_cabecalho(oled, MENU[selecionado][0])
    oled.text(resultado, 0, 28)
    oled.text("3: VOLTAR", 0, 56)
    oled.show()



def desenhar_tela(oled, tela, snapshot):
    conexao, telas = snapshot
    oled.fill(0)
    desenhar_cabecalho(oled, TITULOS[tela])
    oled.text("{}/{}".format(tela + 1, len(TITULOS)), 104, 4)

    if telas is None:
        oled.text("Aguardando dados", 0, 28)
        oled.text(conexao, 0, 47)
    else:
        linhas, percentual = telas[tela]
        for i, linha in enumerate(linhas):
            oled.text(linha[:16], 0, FAIXA_AMARELA_PX + 3 + i * 10)
        if conexao in ("SEM WIFI", "API FALHOU", "ERRO REDE"):
            oled.text("CACHE " + conexao, 0, 54)
        elif conexao == "ALERTA":
            oled.text("NENZA / ALERTA", 0, 54)
        elif percentual is not None:
            oled.rect(0, 51, 128, 10, 1)
            largura = int(percentual * 124 / 100)
            if largura:
                oled.fill_rect(2, 53, largura, 6, 1)
        else:
            oled.text("NENZA / LIVE", 0, 54)
    oled.show()
