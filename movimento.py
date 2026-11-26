from framebuf import FrameBuffer, MONO_VLSB
from time import ticks_diff


def linear(t):
    return t


def ease_in(t):
    return t * t


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return t * t * (3 - 2 * t)


def mola(t):
    u = t - 1
    return 1 + u * u * (2.35 * u + 1.35)


class Movimento:
    def __init__(self, valor=0):
        self.origem = self.alvo = valor
        self.inicio = self.duracao = 0
        self.curva = linear

    def ativo(self, agora):
        if self.origem == self.alvo:
            return False
        if ticks_diff(agora, self.inicio) >= self.duracao:
            self.origem = self.alvo
            return False
        return True

    def valor(self, agora):
        if not self.ativo(agora):
            return self.alvo
        t = max(0, ticks_diff(agora, self.inicio)) / self.duracao
        return self.origem + (self.alvo - self.origem) * self.curva(t)

    def mover(self, alvo, agora, duracao, curva=ease_out):
        self.origem = self.valor(agora)
        self.alvo = alvo
        self.inicio = agora
        self.duracao = duracao
        self.curva = curva

    def fixar(self, valor):
        self.origem = self.alvo = valor


# Mascaras ordenadas de 2x2 nas paginas verticais do SSD1306.
MASCARAS = ((0, 0), (85, 0), (85, 170), (255, 170), (255, 255))


class Transicao:
    def __init__(self, oled):
        self.anterior = bytearray(len(oled.buffer))
        self.entrada = bytearray(len(oled.buffer))
        self.origem = FrameBuffer(self.anterior, oled.width, oled.height, MONO_VLSB)
        self.destino = FrameBuffer(self.entrada, oled.width, oled.height, MONO_VLSB)
        self.fase = Movimento(1)
        self.eixo = 0

    def iniciar(self, oled, agora, eixo):
        self.anterior[:] = oled.buffer
        self.eixo = eixo
        self.fase.fixar(0)
        self.fase.mover(1, agora, 230, ease_in_out)

    def aplicar(self, oled, agora):
        fase = self.fase.valor(agora)
        if fase >= 1:
            return
        if self.eixo == 0:
            par, impar = MASCARAS[min(4, int(fase * 5))]
            for i in range(0, len(self.anterior), 2):
                oled.buffer[i] = (oled.buffer[i] & par) | (self.anterior[i] & (255 ^ par))
                oled.buffer[i + 1] = (oled.buffer[i + 1] & impar) | (self.anterior[i + 1] & (255 ^ impar))
            return
        self.entrada[:] = oled.buffer
        oled.fill(0)
        if self.eixo == 1:
            passo = int(oled.width * fase)
            oled.blit(self.origem, -passo, 0)
            oled.blit(self.destino, oled.width - passo, 0)
        else:
            passo = int(oled.height * fase)
            oled.blit(self.origem, 0, passo)
            oled.blit(self.destino, 0, passo - oled.height)
