# 🦀 MoltyClaw v2026.5.4-1 — O Update da Elite Local & Inteligência Proativa 🏠🧠

## O MoltyClaw evolui de um "Wrapper" para um Sistema Operacional de Agentes Autônomos

Esta release marca o maior salto tecnológico desde o lançamento inicial. Tudo o que você vê abaixo é **NOVO** em relação à versão v26.25.3. Saímos da automação simples para um sistema de soberania local, memória vetorial e proatividade agendada.

---

## ✨ Novidades (O que há de novo)

### 🏠 1. Soberania Local com Ollama

- **Suporte Nativo ao Ollama**: Agora você pode rodar o MoltyClaw 100% offline usando Llama 3, Mistral, Phi-3 e outros, sem depender de nuvens externas.
- **Menu de Lançamento Tático**: Ollama adicionado como opção direta no menu principal (`moltyclaw`), permitindo alternar para o provedor local em segundos antes de iniciar os bots.
- **Auto-Discovery de Modelos**: No `moltyclaw onboard`, o sistema agora detecta seu Ollama local, consulta a API e oferece uma lista dos seus modelos baixados para seleção instantânea.
- **Streaming & Retry Inteligente**: Tratamento de chunks em tempo real e detecção de instabilidade para garantir que o agente não "caia" durante trocas de modelos pesados no seu hardware.

### 🧠 2. Memória Híbrida RAG (Vector + Keyword)

- **Zero-Dep Vector Search**: Motor de busca semântica nativo em `memory_rag.py` com estratégia `sqlite-vec` para alta performance.
- **Busca Semântica**: O agente agora pode procurar parágrafos específicos no seu `MEMORY.md` usando embeddings, mas com cache local em JSON para manter o projeto leve e sem dependências pesadas de DB.
- **Persistência de Longo Prazo**: Combina similaridade de cosseno com busca por palavra-chave para garantir que a IA nunca esqueça fatos cruciais de sessões passadas.

### 🧩 3. Sistema de Skills Modulares (`SKILL_USE`)

- **Economia de Tokens**: As instruções complexas (como GitFlow, Organização de Arquivos ou Análise de Código) agora são "Habilidades" (Skills) preguiçosas.
- **Invocação Sob Demanda**: O agente agora possui a ferramenta `SKILL_USE`. Ele só carrega o prompt pesado de uma habilidade específica quando decide que precisa dela, mantendo o contexto limpo para o raciocínio central.

### ⏰ 4. Scheduler & Heartbeat (Ciclos de Consciência)

- **Proatividade Real**: Introduzimos o `scheduler.py` e o `heartbeat.py`. O MoltyClaw agora pode "acordar" sozinho em intervalos definidos (ex: a cada 15 min) para monitorar e-mails, redes sociais ou o terminal sem intervenção humana.
- **Background Jobs**: Configure tarefas recorrentes diretamente pela WebUI para que seu agente trabalhe de forma autônoma 24/7.

### 🛡️ 5. Ritual de Despertar (BOOTSTRAP.md)

- **Criação de Identidade Guiada**: Ao nascer, um novo agente agora recebe um `BOOTSTRAP.md` com um ritual de despertar. Ele deve conversar com você para definir seu nome, emoji e personalidade antes de deletar o guia e assumir sua forma final no `SOUL.md`.
- **Onboarding Wizard Multi-Canal**: O comando `onboard` agora permite configurar Discord, Telegram, WhatsApp, X, Bluesky, Gmail e Spotify de uma só vez via checkboxes interativos.

### 🏗️ 6. Gestão de Swarm & Sub-Agentes

- **Sub-Agent Registry**: Novo sistema de rastreamento de tarefas em background (`subagent_registry.py`). O Master agora monitora exatamente o que cada sub-agente está fazendo, com status de "pending" a "done".
- **Comando de Status**: O Master agora pode mostrar para você um resumo de todos os agentes que estão trabalhando em segundo plano.

### 🌐 7. Navegação Web & Tooling Hardening

- **Interação Dinâmica**: Adição da ferramenta `SCROLL_DOWN` para lidar com sites de scroll infinito.
- **Core Hardening**: Correção na captura de tags `<tool>` para teclas especiais (`PRESS_ENTER`, `PRESS_KEY`) que antes falhavam em modelos menores.
- **Central Config Service**: Toda a configuração do projeto agora é centralizada em um `moltyclaw.json` com geração automática de tokens de segurança.

> ⚠️ Lembrete de aviso: o Arquivo `.env` ainda funciona, porém será descontinuado em futuras atualizações.
---

## 📁 Evolução da Estrutura

| Novo Arquivo/Módulo          | Função no v26.5.4                                                |
|------------------------------|------------------------------------------------------------------|
| `src/memory_rag.py`          | Motor de busca vetorial para memória de longo prazo.             |
| `src/skills.py`              | Gerenciador de capacidades modulares e dinâmicas.                |
| `src/scheduler.py`           | Orquestrador de tarefas agendadas e proativas.                   |
| `src/heartbeat.py`           | Loop de "pulsação" para monitoramento em background.             |
| `src/subagent_registry.py`   | Rastreamento em tempo real do enxame de sub-agentes ativos.      |
| `moltyclaw.json`             | Registro central de provedores, canais e segurança da gateway.   |

---

## 🚀 Como Explorar as Novas Funções?

1. **Atualize o sistema**: `moltyclaw update`
2. **Reconfigure tudo**: `moltyclaw onboard` (aproveite para testar o Ollama!)
3. **Abra o Painel**: `moltyclaw gateway` e veja a aba de **Scheduler**, **Skills** e o monitoramento de **Agents**.

> ⚠️ Lembrete de Segurança: Com grandes poderes, vêm grandes responsabilidades. O MoltyClaw v26.5.4 tem acesso proativo ao seu sistema. Revise seu `SOUL.md` para garantir que o agente entenda seus limites éticos e operacionais.
