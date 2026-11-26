from config import DIAGNOSTICO_MEMORIA

if DIAGNOSTICO_MEMORIA:
    from diagnostico import medir_memoria
    medir_memoria("Inicializacao", flash=True)

from machine import PWM, Pin, SoftI2C
from ssd1306 import SSD1306_I2C
from time import sleep_ms, ticks_add, ticks_diff, ticks_ms, time
from config import (
    AMOSTRAS, ANIMACOES, GRAFICOS, GRAFICOS_REDE, INATIVIDADE_MS, POMODORO_MS, TITULOS,
    QUADRO_ESPECTRO_MS, QUADRO_MS, GPIO_BOTOES, GPIO_CONFIRMAR, GPIO_ENCODER,
    TRANSICOES_ENCODER,
)
from animacoes import (
    CICLO_MS, CICLO_DVD_MS, LARGURA_TITULO, desenhar_espectro, desenhar_gato,
    desenhar_nenza_dvd, desenhar_onda, desenhar_vu, titulo_oled,
    desenhar_boot, desenhar_ambiente, AudioVisual,
)
from vu_serial import VUSerial
from bmp280 import HistoricoBMP280
from movimento import Movimento, Transicao, ease_in_out, mola
from perifericos import Botao, Encoder, ler_config, salvar_config
from telas import (
    ACOES_FAVORITAS, CONFIG_VOLTAR, CONFIG_WIFI, MENU, PAGINA_ALTITUDE, TITULOS_CLIMA, PASSO_CARROSSEL,
    desenhar_acao, desenhar_clima, desenhar_config,
    desenhar_foco, desenhar_grafico, desenhar_menu, desenhar_painel, desenhar_tela,
)
import monitor

if DIAGNOSTICO_MEMORIA:
    medir_memoria("Modulos carregados")


def main():
    from esp32 import NVS

    led_servidor = PWM(Pin(23, Pin.OUT, value=0), freq=1000, duty=0)
    i2c = SoftI2C(sda=Pin(5), scl=Pin(18), freq=400_000)
    oled = SSD1306_I2C(128, 64, i2c, addr=0x3C)
    oled.rotate(0)  # Gira 180 graus em relação à orientação padrão do driver.
    botoes = tuple(Botao(pino) for pino in GPIO_BOTOES)
    if GPIO_CONFIRMAR is not None:
        botoes += (Botao(GPIO_CONFIRMAR),)
    encoder = Encoder(GPIO_ENCODER, TRANSICOES_ENCODER) if GPIO_ENCODER is not None else None
    tecla_volta = "3" if GPIO_CONFIRMAR is not None else "2L"
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
    bateria_exibida = None
    pagina_clima = None
    revisao_clima_exibida = None
    minuto_exibido = None
    valores_grafico = [None] * AMOSTRAS
    aviso_menu = None
    item_config = None
    editando = False
    exibido = None
    carrossel = Movimento()
    indice_carrossel = None
    tela_exibida = None
    transicao = Transicao(oled)
    progresso = Movimento()
    relevo = Movimento()
    audio = AudioVisual()
    estado_painel_exibido = None
    quadro_animado = False
    tela_bateria = TITULOS.index("BATERIA")
    redesenhar = True

    ultimo_clique = ticks_ms()
    clima = HistoricoBMP280(ultimo_clique)
    try:
        import _thread
        monitor.trava_historico = _thread.allocate_lock()
        _thread.start_new_thread(monitor.atualizar_servidor, (clima,))
    except Exception as erro:
        monitor.estado = ("ERRO REDE", None)
        print("Monitor:", erro)

    ultimo_diagnostico = ultimo_clique
    ultimo_quadro = ultimo_clique
    ultimo_oled = ticks_add(ultimo_clique, -QUADRO_ESPECTRO_MS)
    inicio_boot = ticks_ms()
    descanso = False
    fase = 0
    acao_exibida = None
    quadro_vu = None
    quadro_espectro = None
    quadro_onda = None
    ultimo_titulo = titulo = ""
    fase_titulo = 0
    inicio_pulso_led = ultimo_clique
    periodo_led_anterior = 0
    brilho_led_anterior = 0

    while True:
        agora = ticks_ms()
        vu.atualizar(agora)
        clima.atualizar(agora)
        snapshot = monitor.estado
        conexao = snapshot[0]
        periodo_led = 0
        if conexao in ("LIVE", "ALERTA"):
            periodo_led = 2_000
        elif conexao == "CONECTANDO":
            periodo_led = 600

        if periodo_led != periodo_led_anterior:
            inicio_pulso_led = agora
            periodo_led_anterior = periodo_led

        brilho_led = 0
        if periodo_led:
            decorrido = ticks_diff(agora, inicio_pulso_led)
            fase_led = decorrido % periodo_led
            if decorrido >= periodo_led:
                inicio_pulso_led = ticks_add(agora, -fase_led)
            brilho_led = min(fase_led, periodo_led - fase_led) * 2046 // periodo_led
        if brilho_led != brilho_led_anterior:
            led_servidor.duty(brilho_led)
            brilho_led_anterior = brilho_led

        if prazo_foco is not None:
            segundos = max(0, (ticks_diff(prazo_foco, agora) + 999) // 1000)
            redesenhar = redesenhar or segundos != segundos_foco
            segundos_foco = segundos
            if not segundos:
                prazo_foco = None

        deslocamento_menu = 0
        for indice in range(len(botoes) + int(encoder is not None)):
            if indice < len(botoes):
                botao = botoes[indice]
                gesto = botao.gesto(agora)
                if botao.pressionado:
                    inicio_boot = None
                passo = -1 if indice == 0 else 1
                confirmar = indice == 2 or (indice == 1 and gesto == "longo")
            else:
                passo = encoder.ler()
                gesto = "giro" if passo else None
                confirmar = False
            if gesto is not None:
                inicio_boot = None
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
                    if confirmar:
                        prazo_foco = None
                        segundos_foco = None
                        no_menu = True
                    continue
                if gesto == "longo" and indice == 0:
                    if inicio and acao_atalho is None and monitor.acao_pc[0] is None:
                        acao_atalho = ACOES_FAVORITAS[favorito]
                        monitor.acao_pc = (MENU[acao_atalho][1], "EXECUTANDO...")
                    elif item_config is None and no_menu and selecionado in ACOES_FAVORITAS:
                        favorito = ACOES_FAVORITAS.index(selecionado)
                        salvar_config(nvs, "favorito_v3", favorito)
                        aviso_menu = "FAVORITO"
                    continue
                if acao_atalho is not None:
                    if confirmar:
                        acao_atalho = None
                    continue
                if inicio:
                    if confirmar:
                        inicio = False
                        no_menu = True
                    else:
                        metrica = (metrica + passo) % len(GRAFICOS)
                elif pagina_clima is not None:
                    if confirmar:
                        pagina_clima = None
                        no_menu = True
                    else:
                        pagina_clima = (pagina_clima + passo) % len(TITULOS_CLIMA)
                elif item_config is not None:
                    if confirmar:
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
                        deslocamento_menu += passo
                    else:
                        animacao = (animacao + passo) % len(ANIMACOES)
                elif confirmar:
                    destino = MENU[selecionado][1]
                    if not no_menu:
                        no_menu = True
                    elif destino == "config":
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
                    deslocamento_menu += passo
                    no_menu = True
                redesenhar = True

        resultado_pc = monitor.acao_pc
        minuto_painel = time() // 60 if painel and not descanso else None
        clima_painel = clima.atual
        bateria_painel = None
        if painel and snapshot[0] in ("LIVE", "ALERTA") and snapshot[1]:
            bateria_painel = snapshot[1][tela_bateria][1]
        destino = MENU[selecionado][1]
        menu_principal = no_menu and item_config is None
        rodape_menu = aviso_menu or snapshot[0]
        if segundos_foco is not None:
            tela_atual = ("foco",)
        elif acao_atalho is not None:
            tela_atual = ("acao", acao_atalho)
        elif painel:
            tela_atual = ("painel",)
        elif inicio:
            tela_atual = ("grafico", metrica)
        elif pagina_clima is not None:
            tela_atual = ("clima", pagina_clima)
        elif item_config is not None:
            tela_atual = ("editar",) if editando else ("ajustes",)
        elif no_menu:
            tela_atual = ("menu",)
        else:
            tela_atual = ("detalhe", selecionado)

        troca_tela = tela_atual != tela_exibida
        if tela_atual[0] in ("menu", "ajustes"):
            indice = selecionado if menu_principal else item_config
            total = len(MENU) if menu_principal else CONFIG_VOLTAR + 1
            if troca_tela:
                carrossel.fixar(indice * PASSO_CARROSSEL)
            elif indice != indice_carrossel:
                passo = (indice - indice_carrossel) % total
                if deslocamento_menu < 0:
                    passo -= total
                alvo = carrossel.alvo + passo * PASSO_CARROSSEL
                atual = carrossel.valor(agora)
                # Limita o atraso visual e recentraliza a coordenada circular.
                limite = 2 * PASSO_CARROSSEL
                atual = max(alvo - limite, min(alvo + limite, atual))
                periodo = total * PASSO_CARROSSEL
                carrossel.fixar(atual - alvo + alvo % periodo)
                carrossel.mover(alvo % periodo, agora, 220, mola)
            indice_carrossel = indice
        else:
            carrossel.fixar(0)

        tela_detalhe = tela_atual[0] == "detalhe"
        percentual = None
        if tela_detalhe and isinstance(destino, int) and snapshot[1] is not None:
            percentual = snapshot[1][destino][1]
        if percentual is None:
            progresso.fixar(0)
        else:
            if troca_tela:
                progresso.fixar(0)
            if percentual != progresso.alvo:
                progresso.mover(percentual, agora, 420, ease_in_out)

        if painel and not descanso and (troca_tela or clima_painel != clima_exibido
                       or minuto_painel != minuto_exibido
                       or bateria_painel != bateria_exibida):
            # O dado muda de imediato; somente o logo recebe o pulso visual.
            if not relevo.ativo(agora):
                relevo.fixar(2)
                relevo.mover(0, agora, 380, ease_in_out)
        grafico_clima = metrica >= len(GRAFICOS_REDE)
        revisao_grafico = monitor.historico_clima if grafico_clima else monitor.revisao_historico
        revisao_clima = clima.atual[1] if pagina_clima == PAGINA_ALTITUDE else clima.resumo.bloco
        animando = (carrossel.ativo(agora) or transicao.fase.ativo(agora)
                    or progresso.ativo(agora) or (painel and relevo.ativo(agora)))
        fim_animacao = quadro_animado and not animando
        pronto = ticks_diff(agora, ultimo_oled) >= QUADRO_ESPECTRO_MS
        if inicio_boot is not None:
            fase_boot = ticks_diff(agora, inicio_boot)
            if fase_boot >= 920:
                inicio_boot = None
            elif pronto:
                desenhar_boot(oled, fase_boot)
                ultimo_oled = agora
                tela_exibida = ("boot",)
        if inicio_boot is not None:
            pass
        elif segundos_foco is None and (
            descanso or ticks_diff(agora, ultimo_clique) >= INATIVIDADE_MS
        ):
            intervalo = ticks_diff(agora, ultimo_quadro)
            periodo = QUADRO_ESPECTRO_MS if animacao in (3, 4) else QUADRO_MS
            if pronto and (not descanso or intervalo >= periodo):
                if animacao in (2, 3):
                    if not descanso:
                        audio.reiniciar(agora)
                    audio.atualizar(vu, agora)
                if animacao == 3:
                    if vu.titulo != ultimo_titulo:
                        ultimo_titulo = vu.titulo
                        titulo = titulo_oled(ultimo_titulo)
                        fase_titulo = 0
                    elif not descanso:
                        fase_titulo = 0
                    elif len(titulo) * 8 > LARGURA_TITULO:
                        fase_titulo = (fase_titulo + intervalo) % ((len(titulo) + 3) * 8 * 80)
                    bandas = audio.bandas if vu.bandas is not None or audio.tem_bandas() else None
                    quadro = (bandas, vu.prazo is not None, time() // 60, titulo, fase_titulo // 80)
                    if not descanso or bandas is not None or quadro != quadro_espectro:
                        desenhar_espectro(oled, *quadro)
                        quadro_espectro = quadro
                elif animacao == 4:
                    quadro = (vu.onda, vu.prazo is not None, time() // 60)
                    if not descanso or quadro != quadro_onda:
                        desenhar_onda(oled, *quadro)
                        quadro_onda = quadro
                elif animacao == 2:
                    nivel = int(audio.nivel * 20 + 0.5) / 20
                    quadro = (nivel, vu.pico, vu.prazo is not None or nivel >= 0.1)
                    if not descanso or quadro != quadro_vu:
                        desenhar_vu(oled, *quadro)
                        quadro_vu = quadro
                else:
                    ciclo = CICLO_DVD_MS if animacao == 1 else CICLO_MS if animacao == 0 else 24_000
                    fase = (fase + intervalo) % ciclo if descanso else 0
                    if animacao == 1:
                        desenhar_nenza_dvd(oled, fase)
                    elif animacao == 0:
                        desenhar_gato(oled, fase, snapshot[0] != "LIVE")
                    else:
                        desenhar_ambiente(oled, animacao, fase)
                ultimo_quadro = agora
                ultimo_oled = agora
                tela_exibida = ("descanso",)
                descanso = True
        elif pronto and (
            redesenhar
            or troca_tela
            or animando
            or fim_animacao
            or (menu_principal and rodape_menu != rodape_menu_exibido)
            or (tela_detalhe and isinstance(destino, int) and snapshot is not exibido)
            or ((acao_atalho is not None or (tela_detalhe and isinstance(destino, str)))
                and resultado_pc is not acao_exibida)
            or (painel and (
                monitor.revisao_historico != painel_exibido
                or clima_painel != clima_exibido
                or bateria_painel != bateria_exibida
                or minuto_painel != minuto_exibido
                or conexao != estado_painel_exibido
            ))
            or (inicio and acao_atalho is None and (
                revisao_grafico != historico_exibido
                or (not grafico_clima and (exibido is None or snapshot[0] != exibido[0]))
            ))
            or (pagina_clima is not None and revisao_clima != revisao_clima_exibida)
        ):
            if troca_tela and tela_exibida is not None:
                origem = tela_exibida[0]
                atual = tela_atual[0]
                if origem in ("boot", "descanso"):
                    eixo = 0
                else:
                    eixo = -1 if atual == "menu" else 1
                transicao.iniciar(oled, agora, eixo)
            if segundos_foco is not None:
                desenhar_foco(oled, segundos_foco, tecla_volta)
            elif acao_atalho is not None:
                desenhar_acao(oled, acao_atalho, resultado_pc[1], tecla_volta)
            elif painel:
                painel_exibido, amostra = monitor.ultima_amostra()
                clima_exibido = clima_painel
                bateria_exibida = bateria_painel
                desenhar_painel(oled, amostra, minuto_painel * 60, clima_painel,
                                bateria_painel, conexao, round(relevo.valor(agora)))
                estado_painel_exibido = conexao
                minuto_exibido = minuto_painel
            elif inicio:
                if grafico_clima:
                    historico_exibido = revisao_grafico
                    conexao, pontos = historico_exibido
                    quantidade = len(pontos)
                    coluna = metrica - len(GRAFICOS_REDE)
                    for indice in range(quantidade):
                        valores_grafico[indice] = pontos[indice][coluna]
                else:
                    historico_exibido, quantidade = monitor.copiar_metrica(metrica, valores_grafico)
                    conexao = snapshot[0]
                desenhar_grafico(oled, metrica, valores_grafico, quantidade, conexao, tecla_volta)
            elif pagina_clima is not None:
                desenhar_clima(oled, pagina_clima, clima.resumo, clima.atual[1], tecla_volta)
                revisao_clima_exibida = revisao_clima
            elif item_config is not None:
                if editando:
                    desenhar_config(oled, animacao, tecla_volta + " OK")
                else:
                    desenhar_menu(oled, item_config, "Ajustes", carrossel.valor(agora),
                                  tecla_volta + " OK", ajustes=True)
            elif no_menu:
                desenhar_menu(oled, selecionado, rodape_menu, carrossel.valor(agora),
                              tecla_volta + " OK")
                rodape_menu_exibido = rodape_menu
            elif isinstance(destino, int):
                desenhar_tela(oled, destino, snapshot, progresso.valor(agora))
            else:
                desenhar_acao(oled, selecionado, resultado_pc[1], tecla_volta)
            exibido = snapshot
            acao_exibida = resultado_pc
            transicao.aplicar(oled, agora)
            oled.show()
            ultimo_oled = agora
            tela_exibida = tela_atual
            quadro_animado = animando or transicao.fase.ativo(agora)
            redesenhar = False

        if DIAGNOSTICO_MEMORIA and ticks_diff(agora, ultimo_diagnostico) >= 60_000:
            medir_memoria("Operacao", coletar=False)
            ultimo_diagnostico = agora
        sleep_ms(5)


if __name__ == "__main__":
    main()
