from framebuf import FrameBuffer, MONO_VLSB
from math import sin
from time import gmtime, ticks_diff
from movimento import ease_in_out
from config import BANDAS_ESPECTRO, FAIXA_AMARELA_PX, QUADRO_MS

# Desenho procedural em 128x64, sem bitmaps na flash.
CICLO_MS = 19_200
# O logo de 10 pixels se move apenas na área azul.
CURSO_Y_DVD = 64 - FAIXA_AMARELA_PX - 10
CICLO_DVD_MS = 86 * CURSO_Y_DVD * QUADRO_MS * 2
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


class AudioVisual:
    def __init__(self):
        self.bandas = [0.0] * BANDAS_ESPECTRO
        self.nivel = 0.0
        self.ultimo = 0

    def reiniciar(self, agora):
        self.ultimo = agora
        self.nivel = 0.0
        for i in range(BANDAS_ESPECTRO):
            self.bandas[i] = 0.0

    def atualizar(self, vu, agora):
        dt = max(0, ticks_diff(agora, self.ultimo))
        self.ultimo = agora
        ataque = dt / (dt + 45)
        queda = dt / (dt + 160)
        self.nivel += (vu.nivel - self.nivel) * (ataque if vu.nivel > self.nivel else queda)
        for i in range(BANDAS_ESPECTRO):
            alvo = vu.bandas[i] if vu.bandas is not None else 0
            valor = self.bandas[i]
            self.bandas[i] = valor + (alvo - valor) * (ataque if alvo > valor else queda)

    def tem_bandas(self):
        return any(valor >= 0.2 for valor in self.bandas)


def desenhar_vu(oled, nivel, pico, conectado):
    oled.fill(0)
    rodape = 64 - FAIXA_AMARELA_PX
    oled.text("VU USB", 4, rodape + 4)
    if conectado:
        oled.text("{:2d}/10".format(round(nivel)), 84, rodape + 4)
        for indice in range(10):
            x = 7 + 12 * indice
            altura = int((8 + 3 * indice) * max(0, min(1, nivel - indice)))
            if altura:
                oled.fill_rect(x, 43 - altura, 7, altura, 1)
            else:
                oled.hline(x, 42, 7, 1)
            if indice + 1 == pico:
                oled.hline(x, 33 - 3 * indice, 7, 1)
    else:
        oled.text("Aguardando USB", 8, 22)
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
            altura = int(bandas[indice] * (base - 12) / 10)
            if altura:
                x = 5 + 10 * indice
                oled.hline(x + 1, base - altura, 5, 1)
                if altura > 1:
                    oled.fill_rect(x, base - altura + 1, 7, altura - 1, 1)
    else:
        mensagem = "Sem espectro" if conectado else "Aguardando USB"
        oled.text(mensagem, (128 - len(mensagem) * 8) // 2, 18)
    oled.show()


def reflexo(posicao, limite):
    passo = posicao % (2 * limite)
    return min(passo, 2 * limite - passo)


def desenhar_nenza_dvd(oled, fase):
    x = reflexo(10 + fase * 2 // QUADRO_MS, 86)
    y = FAIXA_AMARELA_PX + reflexo(10 + fase // QUADRO_MS, CURSO_Y_DVD)
    oled.fill(0)
    desenhar_logo_nenza(oled, x, y)
    oled.show()


def desenhar_onda(oled, pontos, conectado, minuto_utc):
    oled.fill(0)
    desenhar_relogio(oled, minuto_utc)
    if pontos is None:
        mensagem = "Sem onda" if conectado else "Aguardando USB"
        oled.text(mensagem, (128 - len(mensagem) * 8) // 2, 34)
    else:
        topo = FAIXA_AMARELA_PX
        amplitude = (63 - topo) // 2
        centro = topo + amplitude + 1
        for x in range(2, 128, 8):
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
    respiracao = round(2 * sin(fase * 6.283 / 3200))
    ciclo, fase = divmod(fase, 6400)
    if fase < 1500:
        olhar = 0
    elif fase < 3000:
        olhar = min(9, (fase - 1500) // 35)
    elif fase < 4650:
        olhar = max(-9, 9 - (fase - 3000) // 35)
    else:
        olhar = min(0, -9 + (fase - 4650) // 35)

    if ciclo == 1:
        olhar = -olhar
    elif ciclo == 2:
        olhar //= 2
    raio_y = 1 if dormindo else 12 + respiracao // 2
    if not dormindo:
        for piscada in (1140, 3810, 4100, 5680):
            distancia = abs(fase - piscada - 240 * ciclo)
            raio_y = min(raio_y, max(1, (distancia - 20) // 6))

    oled.fill(0)

    # Orelhas e interior das orelhas.
    for x, lado in ((17, 1), (110, -1)):
        x += respiracao * lado
        oled.line(x, 15, x + lado * 3, 2, 1)
        oled.line(x + lado * 3, 2, x + lado * 22, 15, 1)
        oled.line(x + lado * 6, 7, x + lado * 13, 13, 1)

    for x in (35, 92):
        if raio_y <= 2:
            oled.line(x - 19, 33, x - 8, 37, 1)
            oled.hline(x - 8, 37, 17, 1)
            oled.line(x + 8, 37, x + 19, 33, 1)
        else:
            oled.ellipse(x, 33 + respiracao, 22, raio_y, 1, True)
            pupila = x + olhar
            oled.ellipse(pupila, 33 + respiracao, 4, raio_y - 1, 0, True)
            if raio_y >= 7:
                oled.fill_rect(pupila - 2, 28 + respiracao, 3, 3, 1)
                oled.pixel(pupila + 2, 35 + respiracao, 1)

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



def desenhar_boot(oled, fase):
    oled.fill(0)
    abertura = ease_in_out(min(1, fase / 570))
    raio = int(25 * abertura)
    y = 28 + int(5 * (1 - abertura))
    if raio:
        oled.ellipse(64, y, raio, max(1, int(10 * abertura)), 1)
    if fase >= 240:
        desenhar_logo_nenza(oled, 43, y - 5)
        visivel = int(21 * ease_in_out(min(1, (fase - 240) / 410)))
        margem = 21 - visivel
        if margem:
            oled.fill_rect(43, y - 5, margem, 10, 0)
            oled.fill_rect(85 - margem, y - 5, margem, 10, 0)
    if fase >= 560:
        oled.text("Nenza Corp", 24, 49)
    oled.show()


def desenhar_ambiente(oled, animacao, fase):
    oled.fill(0)
    t = fase * 6.283185 / 24_000
    if animacao == 5:  # Particulas com velocidades e orbitas diferentes.
        for i in range(19):
            x = (i * 37 + int(6 * sin(t * (i % 3 + 1) + i))) % 128
            y = (i * 21 - fase * (i % 3 + 1) * 64 // 24_000) % 64
            oled.pixel(x, y, 1)
            if i % 4 == 0:
                oled.pixel(x + 1, y, 1)
                oled.pixel(x, y + 1, 1)
    elif animacao == 6:  # Estrelas aceleram do centro para as bordas.
        for i in range(26):
            z = ((fase * (1 + i % 2) + i * 1471) % 4800) / 4800
            x = 64 + int(((i * 41 % 129) - 64) * z * z)
            y = 32 + int(((i * 29 % 65) - 32) * z * z)
            oled.pixel(x, y, 1)
            if z > 0.8:
                oled.pixel(x + 1, y, 1)
    elif animacao == 7:
        for i in range(3):
            anterior = 0
            for x in range(0, 128, 4):
                y = 15 + i * 16 + int(6 * sin(x / 17 + t * 4 + i))
                if x:
                    oled.line(x - 4, anterior, x, y, 1)
                anterior = y
    elif animacao == 8:
        for i in range(3):
            x = 63 + int(42 * sin(t * (i + 1) + i * 2))
            y = 31 + int(18 * sin(t * (i + 2) + i))
            if i == 1:
                oled.line(x - 8, y, x, y - 8, 1)
                oled.line(x, y - 8, x + 8, y, 1)
                oled.line(x + 8, y, x, y + 8, 1)
                oled.line(x, y + 8, x - 8, y, 1)
            else:
                oled.ellipse(x, y, 8 + i * 2, 8, 1, i == 2)
    elif animacao == 9:
        altura = min(13, max(1, abs(fase % 3600 - 1700) // 14))
        olhar = int(7 * sin(t * 5))
        for x in (40, 88):
            oled.ellipse(x, 31, 15, altura, 1, True)
            if altura > 2:
                oled.ellipse(x + olhar, 31, 4, altura - 2, 0, True)
    else:
        pulso = (1 + sin(t * 6)) / 2
        oled.ellipse(64, 32, 23 + int(pulso * 11), 10 + int(pulso * 7), 1)
        desenhar_logo_nenza(oled, 43, 27)
    oled.show()
