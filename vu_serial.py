import json
import sys
from select import POLLIN, poll
from time import ticks_add, ticks_diff
from binascii import unhexlify
from config import BANDAS_ESPECTRO, PONTOS_ONDA

NIVEIS_VU = tuple(str(nivel) for nivel in range(11))
PREFIXO_MEDIA = "MEDIA:1:"
PREFIXO_ONDA = "WAVE:1:"
LIMITE_TITULO = 48
# Um caractere Unicode pode ocupar 12 bytes se for enviado como par de escapes.
LIMITE_LINHA = len(PREFIXO_MEDIA) + 2 + LIMITE_TITULO * 12


class VUSerial:
    def __init__(self):
        self.entrada = getattr(sys.stdin, "buffer", sys.stdin)
        self.poll = poll()
        self.poll.register(self.entrada, POLLIN)
        self.linha = bytearray()
        self.descartar = False
        self.nivel = self.pico = 0
        self.bandas = None
        self.onda = None
        self.prazo_onda = None
        self.titulo = ""
        self.prazo_midia = None
        self.prazo = None

    def atualizar(self, agora):
        # Limita o trabalho por volta para manter os botões responsivos.
        for _ in range(64):
            if not self.poll.poll(0):
                break
            caractere = self.entrada.read(1)
            if not caractere:
                break
            dados = caractere.encode("utf-8") if isinstance(caractere, str) else caractere
            if dados == b"\n":
                if not self.descartar:
                    try:
                        linha = bytes(self.linha).decode("utf-8").rstrip("\r")
                    except ValueError:
                        pass
                    else:
                        self.receber(linha, agora)
                self.linha = bytearray()
                self.descartar = False
            elif not self.descartar:
                if len(self.linha) + len(dados) > LIMITE_LINHA:
                    self.descartar = True
                else:
                    self.linha.extend(dados)

        if self.prazo is not None and ticks_diff(agora, self.prazo) >= 0:
            self.prazo = None
            self.nivel = self.pico = 0
            self.bandas = None
        if self.prazo_midia is not None and ticks_diff(agora, self.prazo_midia) >= 0:
            self.prazo_midia = None
            self.titulo = ""
        if self.prazo_onda is not None and ticks_diff(agora, self.prazo_onda) >= 0:
            self.prazo_onda = None
            self.onda = None

    def receber(self, linha, agora):
        if linha == "VU:PING":
            print("VU:READY")
            return
        if linha.startswith(PREFIXO_ONDA):
            if len(linha) != len(PREFIXO_ONDA) + 2 * PONTOS_ONDA:
                return
            try:
                onda = unhexlify(linha[len(PREFIXO_ONDA):])
            except ValueError:
                return
            self.onda = onda
            self.prazo_onda = ticks_add(agora, 1500)
            return
        if linha.startswith(PREFIXO_MEDIA):
            try:
                titulo = json.loads(linha[len(PREFIXO_MEDIA):])
            except ValueError:
                return
            if isinstance(titulo, str) and len(titulo) <= LIMITE_TITULO:
                self.titulo = titulo
                # O Windows reenvia o título a cada 3 s, separado dos quadros de áudio.
                self.prazo_midia = ticks_add(agora, 10_000) if titulo else None
            return
        campos = linha.split(":")
        if campos[0] == "SPEC":
            if len(campos) != 5 or campos[1] != "1":
                return
            nivel, pico = campos[2:4]
            bandas = campos[4].split(",")
            if len(bandas) != BANDAS_ESPECTRO or not all(banda in NIVEIS_VU for banda in bandas):
                return
            if nivel not in NIVEIS_VU or pico not in NIVEIS_VU:
                return
            self.bandas = tuple(int(banda) for banda in bandas)
            self.nivel, self.pico = int(nivel), int(pico)
            self.prazo = ticks_add(agora, 1500)
            return
        if campos[0] != "VU" or len(campos) not in (2, 3):
            return
        if not all(campo in NIVEIS_VU for campo in campos[1:]):
            return
        self.nivel = int(campos[1])
        self.pico = int(campos[-1])
        self.bandas = None
        self.prazo = ticks_add(agora, 1500)
