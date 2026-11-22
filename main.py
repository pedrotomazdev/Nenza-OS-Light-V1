from config import DIAGNOSTICO_ENCODER, DIAGNOSTICO_MEMORIA

if DIAGNOSTICO_MEMORIA:
    from diagnostico import medir_memoria
    medir_memoria("Inicializacao", flash=True)

from machine import Pin, SoftI2C
from ssd1306 import SSD1306_I2C
from time import sleep_ms, ticks_add, ticks_diff, ticks_ms, time
from config import (
    AMOSTRAS, ANIMACOES, GRAFICOS, GRAFICOS_REDE, INATIVIDADE_MS, POMODORO_MS,
    QUADRO_ESPECTRO_MS, QUADRO_MS,
)
from animacoes import (
    CICLO_MS, CICLO_DVD_MS, LARGURA_TITULO, desenhar_espectro, desenhar_gato,
    desenhar_nenza_dvd, desenhar_onda, desenhar_vu, titulo_oled,
)
from vu_serial import VUSerial
from bmp280 import HistoricoBMP280
from perifericos import Botao, EncoderRotativo, ler_config, salvar_config
from telas import (
    ACOES_FAVORITAS, CONFIG_VOLTAR, CONFIG_WIFI, MENU, PAGINA_ALTITUDE, TITULOS_CLIMA,
    desenhar_acao, desenhar_clima, desenhar_config,
    desenhar_foco, desenhar_grafico, desenhar_menu, desenhar_painel, desenhar_tela,
)
import monitor 

if DIAGNOSTICO_MEMORIA:
    medir_memoria("Modulos carregados")


def main():
    from esp32 import NVS

    i2c = SoftI2C(sda=Pin(5), scl=Pin(18), freq=400_000)
    oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
    oled.rotate(0)  # Gira 180 graus em relação à orientação padrão do driver.
    botoes = (Botao(33), Botao(27), Botao(26))
    nvs = NVS("nenza_menu")
    if ler_config(nvs, "portal_wifi", 0, 1):
        print("[CONFIG] Portal aberto por solicitacao do menu")
        try:
            nvs.set_i32("portal_wifi", 0)
            nvs.commit()
            from portal_config import executar
            executar(oled)
        except (ImportError, OSError, ValueError, MemoryError) as erro:
            print("[CONFIG] Falha no portal:", erro)
            oled.fill(0)
            oled.text("ERRO NO PORTAL", 0, 24)
            oled.show()
            sleep_ms(1500)
    animacao = ler_config(nvs, "animacao", 0, len(ANIMACOES) - 1)
    encoder = EncoderRotativo(4, 15)
    if DIAGNOSTICO_ENCODER:
        print("[ENCODER] GPIO4=A GPIO15=B |", encoder.TRANSICOES_POR_PASSO, "transicoes por passo")
        encoder.mostrar_diagnostico(ticks_ms())
    vu = VUSerial()
    selecionado = 0
    no_menu = False
    painel = True
    inicio = False
    metrica = 0
    # Na lista original, "Testar conexao" ocupava o indice 2.
    anterior = ler_config(nvs, "favorito", 0, len(ACOES_FAVORITAS) + 1)
    padrao_favorito = 0 if anterior == 2 else anterior - int(anterior > 2)
    anterior = ler_config(nvs, "favorito_v2", padrao_favorito, len(ACOES_FAVORITAS))
    # Na segunda lista, "Minimizar Nenza" ocupava o indice 1.
    padrao_favorito = max(0, anterior - 1)
    favorito = ler_config(nvs, "favorito_v3", padrao_favorito, len(ACOES_FAVORITAS) - 1)
    acao_atalho = None
    prazo_foco = None
    segundos_foco = None
    historico_exibido = None
    painel_exibido = None
    clima_exibido = None
    pagina_clima = None
    revisao_clima_exibida = None
    minuto_exibido = None
    valores_grafico = [None] * AMOSTRAS
    aviso_menu = None
    item_config = None
    editando = False
    exibido = None
    redesenhar = True

    try:
        import _thread
        monitor.trava_historico = _thread.allocate_lock()
        _thread.start_new_thread(monitor.atualizar_servidor, ())
    except Exception as erro:
        monitor.estado = ("ERRO REDE", None)
        print("Monitor:", erro)

    ultimo_clique = ticks_ms()
    clima = HistoricoBMP280(ultimo_clique)
    ultimo_diagnostico = ultimo_clique
    ultimo_quadro = ultimo_clique
    descanso = False
    fase = 0
    acao_exibida = None
    quadro_vu = None
    quadro_espectro = None
    quadro_onda = None
    ultimo_titulo = titulo = ""
    fase_titulo = 0

    while True:
        agora = ticks_ms()
        encoder.atualizar()
        vu.atualizar(agora)
        clima.atualizar(agora)
        if DIAGNOSTICO_ENCODER:
            encoder.mostrar_diagnostico(agora)
        snapshot = monitor.estado
        if prazo_foco is not None:
            segundos = max(0, (ticks_diff(prazo_foco, agora) + 999) // 1000)
            redesenhar = redesenhar or segundos != segundos_foco
            segundos_foco = segundos
            if not segundos:
                prazo_foco = None

        for indice in range(4):
            if indice == 3:
                passo = encoder.ler_passos()
                if DIAGNOSTICO_ENCODER and passo:
                    print("[ENCODER] movimento", passo)
                gesto = "curto" if passo else None
            else:
                botao = botoes[indice]
                gesto = botao.gesto(agora) if indice == 2 else (
                    "curto" if botao.clicou(agora) else None
                )
                passo = -1 if indice == 0 else 1
            if gesto is not None:
                if indice != 3:
                    print("Botao", indice + 1, "pressionado", gesto)
                ultimo_clique = agora
                acordou = descanso
                descanso = False
                redesenhar = True
                aviso_menu = None
                if painel or acordou:
                    painel = False
                    inicio = False
                    pagina_clima = None
                    no_menu = True
                    acao_atalho = None
                    item_config = None
                    editando = False
                    continue
                if segundos_foco is not None:
                    if indice == 2 and gesto == "curto":
                        prazo_foco = None
                        segundos_foco = None
                        no_menu = True
                    continue
                if gesto == "longo":
                    if inicio and acao_atalho is None and monitor.acao_pc[0] is None:
                        acao_atalho = ACOES_FAVORITAS[favorito]
                        monitor.acao_pc = (MENU[acao_atalho][1], "EXECUTANDO...")
                    elif item_config is None and no_menu and selecionado in ACOES_FAVORITAS:
                        favorito = ACOES_FAVORITAS.index(selecionado)
                        salvar_config(nvs, "favorito_v3", favorito)
                        aviso_menu = "FAVORITO"
                    continue
                if acao_atalho is not None:
                    if indice == 2:
                        acao_atalho = None
                    continue
                if inicio:
                    if indice == 2:
                        inicio = False
                        no_menu = True
                    else:
                        metrica = (metrica + passo) % len(GRAFICOS)
                elif pagina_clima is not None:
                    if indice == 2:
                        pagina_clima = None
                        no_menu = True
                    else:
                        pagina_clima = (pagina_clima + passo) % len(TITULOS_CLIMA)
                elif item_config is not None:
                    if indice == 2:
                        if editando:
                            salvar_config(nvs, "animacao", animacao)
                            editando = False
                        elif item_config == CONFIG_WIFI:
                            from machine import reset

                            try:
                                nvs.set_i32("portal_wifi", 1)
                                nvs.commit()
                            except OSError as erro:
                                print("[CONFIG] Falha ao solicitar portal:", erro)
                                oled.fill(0)
                                oled.text("ERRO AO SALVAR", 0, 24)
                                oled.show()
                                sleep_ms(1500)
                            else:
                                reset()
                        elif item_config == CONFIG_VOLTAR:
                            item_config = None
                        else:
                            editando = True
                    elif not editando:
                        item_config = (item_config + passo) % (CONFIG_VOLTAR + 1)
                    else:
                        animacao = (animacao + passo) % len(ANIMACOES)
                elif indice == 2:
                    destino = MENU[selecionado][1]
                    if destino == "config":
                        item_config = 0
                    elif no_menu and destino == "painel":
                        painel = True
                        no_menu = False
                    elif no_menu and destino == "graficos":
                        inicio = True
                        no_menu = False
                    elif no_menu and destino == "clima":
                        pagina_clima = 0
                        no_menu = False
                    elif no_menu and destino == "pc":
                        prazo_foco = ticks_add(agora, POMODORO_MS)
                        segundos_foco = POMODORO_MS // 1000
                        no_menu = False
                        continue
                    elif no_menu and isinstance(destino, str):
                        if monitor.acao_pc[0] is None:
                            monitor.acao_pc = (destino, "EXECUTANDO...")
                            no_menu = False
                    else:
                        no_menu = not no_menu
                else:
                    selecionado = (selecionado + passo) % len(MENU)
                    no_menu = True
                redesenhar = True

        resultado_pc = monitor.acao_pc
        minuto_painel = time() // 60 if painel and not descanso else None
        grafico_local = metrica >= len(GRAFICOS_REDE)
        revisao_grafico = clima.revisao if grafico_local else monitor.revisao_historico
        revisao_clima = clima.atual[1] if pagina_clima == PAGINA_ALTITUDE else clima.resumo.bloco
        if segundos_foco is None and (
            descanso or ticks_diff(agora, ultimo_clique) >= INATIVIDADE_MS
        ):
            intervalo = ticks_diff(agora, ultimo_quadro)
            periodo = QUADRO_ESPECTRO_MS if animacao in (3, 4) else QUADRO_MS
            if not descanso or intervalo >= periodo:
                if animacao == 3:
                    if vu.titulo != ultimo_titulo:
                        ultimo_titulo = vu.titulo
                        titulo = titulo_oled(ultimo_titulo)
                        fase_titulo = 0
                    elif not descanso:
                        fase_titulo = 0
                    elif len(titulo) * 8 > LARGURA_TITULO:
                        fase_titulo = (fase_titulo + intervalo) % ((len(titulo) + 3) * 8 * 80)
                    quadro = (vu.bandas, vu.prazo is not None, time() // 60, titulo, fase_titulo // 80)
                    if not descanso or quadro != quadro_espectro:
                        desenhar_espectro(oled, *quadro)
                        quadro_espectro = quadro
                elif animacao == 4:
                    quadro = (vu.onda, vu.prazo is not None, time() // 60)
                    if not descanso or quadro != quadro_onda:
                        desenhar_onda(oled, *quadro)
                        quadro_onda = quadro
                elif animacao == 2:
                    quadro = (vu.nivel, vu.pico, vu.prazo is not None)
                    if not descanso or quadro != quadro_vu:
                        desenhar_vu(oled, *quadro)
                        quadro_vu = quadro
                else:
                    ciclo = CICLO_DVD_MS if animacao == 1 else CICLO_MS
                    fase = (fase + intervalo) % ciclo if descanso else 0
                    if animacao == 1:
                        desenhar_nenza_dvd(oled, fase)
                    else:
                        desenhar_gato(oled, fase, snapshot[0] != "LIVE")
                ultimo_quadro = agora
                descanso = True
        elif (
            redesenhar or snapshot is not exibido or resultado_pc is not acao_exibida
            or (painel and (
                monitor.revisao_historico != painel_exibido
                or clima.atual != clima_exibido
                or minuto_painel != minuto_exibido
            ))
            or (inicio and revisao_grafico != historico_exibido)
            or (pagina_clima is not None and revisao_clima != revisao_clima_exibida)
        ):
            destino = MENU[selecionado][1]
            if segundos_foco is not None:
                desenhar_foco(oled, segundos_foco)
            elif acao_atalho is not None:
                desenhar_acao(oled, acao_atalho, resultado_pc[1])
            elif painel:
                painel_exibido, amostra = monitor.ultima_amostra()
                clima_exibido = clima.atual
                desenhar_painel(oled, amostra, minuto_painel * 60, clima_exibido)
                minuto_exibido = minuto_painel
            elif inicio:
                if grafico_local:
                    historico_exibido, quantidade = clima.copiar_metrica(
                        metrica - len(GRAFICOS_REDE), valores_grafico
                    )
                    conexao = None
                else:
                    historico_exibido, quantidade = monitor.copiar_metrica(metrica, valores_grafico)
                    conexao = snapshot[0]
                desenhar_grafico(oled, metrica, valores_grafico, quantidade, conexao)
            elif pagina_clima is not None:
                desenhar_clima(oled, pagina_clima, clima.resumo, clima.atual[1])
                revisao_clima_exibida = revisao_clima
            elif item_config is not None:
                desenhar_config(oled, item_config, editando, animacao)
            elif no_menu:
                desenhar_menu(oled, selecionado, aviso_menu or snapshot[0])
            elif isinstance(destino, int):
                desenhar_tela(oled, destino, snapshot)
            else:
                desenhar_acao(oled, selecionado, resultado_pc[1])
            exibido = snapshot
            acao_exibida = resultado_pc
            redesenhar = False

        if DIAGNOSTICO_MEMORIA and ticks_diff(agora, ultimo_diagnostico) >= 60_000:
            medir_memoria("Operacao", coletar=False)
            ultimo_diagnostico = agora
        # Sonda o encoder durante a pausa do loop, como no teste isolado.
        for _ in range(5):
            sleep_ms(1)
            encoder.atualizar()


if __name__ == "__main__":
    main()
