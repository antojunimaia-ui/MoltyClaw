# 🦀 MoltyClaw v26.5.4

## ✨ Novidades

1. **Bug Fix: Localização Crucial do `.env`**:
   - Correção do erro que fazia ferramentas como `moltyclaw doctor` procurarem o `.env` no diretório de execução atual, ignorando a pasta mestre.
   - Refatoração dos módulos (Discord, Telegram, Twitter, Bluesky, WebUI, Gateway e CLI) para carregarem o `.env` exclusivamente da `MOLTY_DIR` (~/.moltyclaw/).

2. **Melhorias Significativas no Onboarding (`moltyclaw onboard`)**:
   - **Aviso de Segurança**: Adição de um aviso sobre o uso do MoltyClaw sem a devida falta de configuração correta.
   - **Configuração Refinada**: Fluxo de escolha de modelos de IA e provedores mais intuitivo e validado.
   - **Suporte a Integrações**: Novo passo interativo com checkbox para configurar múltiplos canais (Discord, Telegram, WhatsApp, Redes Sociais, Gmail e Spotify) de uma só vez, preenchendo as chaves automaticamente no template mestre.

3. **Gerenciador de Ações Agendadas (CRON / Scheduler)**:
   - Implementação dos módulos `scheduler.py` e `heartbeat.py` para execução de tarefas periódicas em background (ex: monitoramento de redes, leitura de e-mails de forma proativa).

4. **Sistema de Skills Modulares**:
   - Criação do motor de Skills (`skills.py`) para carregamento dinâmico de novas ferramentas e instruções ao prompt do agente.
   - Introdução da ação `SKILL_USE`, permitindo ao robô invocar comportamentos complexos somente sob demanda.

5. **Correção de Ferramentas de Navegação**:
   - Resolvido bug onde tags de ferramenta `<tool>` para teclado (`PRESS_ENTER`, `PRESS_KEY`) não eram capturadas e vinham como texto bruto.
   - Implementação da ferramenta de rolagem de página (`SCROLL_DOWN`) para interação dinâmica via Playwright.

> ⚠️ Lembrete de Segurança: O MoltyClaw opera com as mesmas permissões do seu usuário Windows. Ele tem acesso ao terminal, sistema de arquivos e internet. Use whitelists e revise o SOUL.md para definir limites de comportamento.
