from framebuf import FrameBuffer, MONO_VLSB
from time import gmtime
from config import BANDAS_ESPECTRO, FAIXA_AMARELA_PX, QUADRO_MS

# Desenho procedural em 128x64, sem bitmaps na flash.
CICLO_MS = 6400
# O logo de 10 pixels se move apenas na área azul.
CURSO_Y_DVD = 64 - FAIXA_AMARELA_PX - 10
PERIODO_Y_DVD = 2 * (CURSO_Y_DVD + 1)
CICLO_DVD_MS = 87 * PERIODO_Y_DVD * QUADRO_MS
INICIO_TITULO = 36
LARGURA_TITULO = 128 - INICIO_TITULO
AREA_TITULO = FrameBuffer(bytearray(LARGURA_TITULO), LARGURA_TITULO, 8, MONO_VLSB)
ICONE_RELOGIO = b"\x3c\x42\x89\x89\x85\x81\x42\x3c"
DIGITOS_RELOGIO = (
    (7, 5, 5, 5, 7), (2, 6, 2, 2, 7), (7, 1, 7, 4, 7), (7, 1, 7, 1, 7),
    (5, 5, 7, 1, 1), (7, 4, 7, 1, 7), (7, 4, 7, 5, 7), (7, 1, 1, 1, 1),
    (7, 5, 7, 5, 7), (7, 5, 7, 1, 7), (0, 0, 7, 0, 0), (0, 2, 0, 2, 0),
)
ACENTOS = dict(zip(
    "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ",
    "aaaaaeeeeiiiiooooouuuucnAAAAAEEEEIIIIOOOOOUUUUCN", 
))


def desenhar_logo_nenza(oled, x, y):
    oled.rect(x, y, 42, 10, 1)
    oled.text("NENZA", x + 1, y + 1)


def desenhar_vu(oled, nivel, pico, conectado):
    oled.fill(0)
    rodape = 64 - FAIXA_AMARELA_PX
    oled.rect(0, rodape, 128, FAIXA_AMARELA_PX, 1)
    oled.text("VU USB", 4, rodape + 4)
    if conectado:
        valor = "{:2d}/10".format(nivel)
        oled.text(valor, 84, rodape + 4)
        for indice in range(10):
            x = 5 + 12 * indice
            altura = 8 + 3 * indice
            y = 43 - altura
            if indice < nivel:
                oled.fill_rect(x, y, 10, altura, 1)
            else:
                oled.rect(x, y, 10, altura, 1)
            if indice + 1 == pico:
                oled.hline(x, y - 2, 10, 1)
    else:
        oled.text("AGUARDANDO USB", 8, 22)
    oled.show()


def titulo_oled(titulo):
    # A fonte do FrameBuffer só tem glifos ASCII.
    return "".join(c if " " <= c <= "~" else ACENTOS.get(c, " ") for c in titulo).strip()


def desenhar_relogio(oled, minuto_utc):
    ano, _, _, hora, minuto, *_ = gmtime(max(0, minuto_utc * 60 - 3 * 3600))
    horario = "{:02d}:{:02d}".format(hora, minuto) if ano >= 2025 else "--:--"
    for y, bits in enumerate(ICONE_RELOGIO):
        for x in range(8):
            if bits & (0x80 >> x):
                oled.pixel(x, y, 1)
    for indice, caractere in enumerate(horario):
        glifo = 11 if caractere == ":" else 10 if caractere == "-" else int(caractere)
        for y, bits in enumerate(DIGITOS_RELOGIO[glifo]):
            for x in range(3):
                if bits & (4 >> x):
                    oled.pixel(10 + indice * 4 + x, y + 1, 1)


def desenhar_espectro(oled, bandas, conectado, minuto_utc, titulo, deslocamento):
    oled.fill(0)
    desenhar_relogio(oled, minuto_utc)
    if titulo:
        largura = len(titulo) * 8
        AREA_TITULO.fill(0)
        if largura <= LARGURA_TITULO:
            AREA_TITULO.text(titulo, LARGURA_TITULO - largura, 0)
        else:
            inicio, pixel = divmod(deslocamento, 8)
            faixa = titulo + " | "
            colunas_visiveis = (LARGURA_TITULO + 14) // 8
            trecho = (faixa + faixa)[inicio:inicio + colunas_visiveis]
            AREA_TITULO.text(trecho, -pixel, 0)
        oled.blit(AREA_TITULO, INICIO_TITULO, 0)

    if bandas is not None:
        base = 62
        for indice in range(BANDAS_ESPECTRO):
            altura = bandas[indice] * (base - 10) // 10
            if altura:
                oled.fill_rect(5 + 10 * indice, base - altura, 8, altura, 1)
    else:
        mensagem = "SEM ESPECTRO" if conectado else "AGUARDANDO USB"
        oled.text(mensagem, (128 - len(mensagem) * 8) // 2, 18)
    oled.show()


def desenhar_nenza_dvd(oled, fase):
    quadro = fase // QUADRO_MS
    # Reflete a posicao nos limites de um logo de 42 por 10 pixels.
    x = (10 + 2 * quadro) % 174
    y = (10 + quadro) % PERIODO_Y_DVD
    x = min(x, 173 - x)
    y = FAIXA_AMARELA_PX + min(y, PERIODO_Y_DVD - 1 - y)
    oled.fill(0)
    desenhar_logo_nenza(oled, x, y)
    oled.show()


def desenhar_onda(oled, pontos, conectado, minuto_utc):
    oled.fill(0)
    desenhar_relogio(oled, minuto_utc)
    if pontos is None:
        mensagem = "SEM ONDA" if conectado else "AGUARDANDO USB"
        oled.text(mensagem, (128 - len(mensagem) * 8) // 2, 34)
    else:
        topo = FAIXA_AMARELA_PX
        amplitude = (63 - topo) // 2
        centro = topo + amplitude + 1
        for x in range(0, 128, 4):
            oled.pixel(x, centro, 1)

        x_anterior = 0
        y_anterior = centro - ((pontos[0] - 128) * amplitude // 128)
        for indice in range(1, len(pontos)):
            x = indice * 127 // (len(pontos) - 1)
            y = centro - ((pontos[indice] - 128) * amplitude // 128)
            oled.line(x_anterior, y_anterior, x, y, 1)
            x_anterior, y_anterior = x, y
    oled.show()


def desenhar_gato(oled, fase, dormindo):
    if fase < 1500:
        olhar = 0
    elif fase < 3000:
        olhar = min(9, (fase - 1500) // 35)
    elif fase < 4650:
        olhar = max(-9, 9 - (fase - 3000) // 35)
    else:
        olhar = min(0, -9 + (fase - 4650) // 35)

    raio_y = 1 if dormindo else 13
    if not dormindo:
        for piscada in (1140, 3810, 4100, 5680):
            distancia = abs(fase - piscada)
            raio_y = min(raio_y, max(1, (distancia - 20) // 6))

    oled.fill(0)

    # Orelhas e interior das orelhas.
    for x, lado in ((17, 1), (110, -1)):
        oled.line(x, 15, x + lado * 3, 2, 1)
        oled.line(x + lado * 3, 2, x + lado * 22, 15, 1)
        oled.line(x + lado * 6, 7, x + lado * 13, 13, 1)

    for x in (35, 92):
        if raio_y <= 2:
            oled.line(x - 19, 33, x - 8, 37, 1)
            oled.hline(x - 8, 37, 17, 1)
            oled.line(x + 8, 37, x + 19, 33, 1)
        else:
            oled.ellipse(x, 33, 22, raio_y, 1, True)
            pupila = x + olhar
            oled.ellipse(pupila, 33, 4, raio_y - 1, 0, True)
            if raio_y >= 7:
                oled.fill_rect(pupila - 2, 28, 3, 3, 1)
                oled.pixel(pupila + 2, 35, 1)

    # Nariz, boca e bigodes.
    oled.hline(60, 47, 7, 1)
    oled.hline(61, 48, 5, 1)
    oled.hline(62, 49, 3, 1)
    oled.vline(63, 50, 4, 1)
    oled.line(63, 53, 59, 56, 1)
    oled.line(63, 53, 67, 56, 1)
    oled.line(59, 56, 55, 54, 1)
    oled.line(67, 56, 71, 54, 1)

    for ponta, bochecha in ((3, 25), (124, 102)):
        oled.line(ponta, 47, bochecha, 49, 1)
        oled.line(ponta + (4 if ponta < bochecha else -4), 57, bochecha, 52, 1)

    if dormindo:
        subida = fase % 1600 // 100
        oled.text("Z", 67 + subida // 2, FAIXA_AMARELA_PX + 7 - subida // 2, 1)

    oled.show()
