import os
import sys
import time
import socket
import random
import asyncio
import aiohttp
from playwright.async_api import async_playwright
from config_loader import get_config
from initializer import MOLTY_DIR

class BrowserEngine:
    def __init__(self, agent_name: str = "MoltyClaw", base_dir: str = None, browser_enabled: bool = True, browser_headless: bool = True, console=None):
        self.name = agent_name
        self.base_dir = base_dir or MOLTY_DIR
        self.browser_enabled = browser_enabled
        self.browser_headless = browser_headless
        self.console = console
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def _log(self, text: str, style: str = "info"):
        if self.console:
            try:
                self.console.print(f"[{style}][{self.name}] {text}[/{style}]")
            except UnicodeEncodeError:
                safe_text = text.encode("ascii", errors="replace").decode("ascii")
                try:
                    self.console.print(f"[{style}][{self.name}] {safe_text}[/{style}]")
                except Exception:
                    pass
            except Exception:
                pass

    async def close(self):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None

    async def init(self):
        if not self.browser_enabled:
            return

        await self.close()
        cdp_url = "http://localhost:9222"

        async def _try_cdp_connect() -> bool:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{cdp_url}/json/version", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        if resp.status != 200:
                            return False
                if self.playwright is None:
                    self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
                if self.browser.contexts:
                    self.context = self.browser.contexts[0]
                else:
                    self.context = await self.browser.new_context()
                self.page = await self.context.new_page()
                self._log("🔗 Conectado ao Navegador Compartilhado (Master já estava ativo)!", "info")
                return True
            except Exception:
                return False

        if await _try_cdp_connect():
            return

        await asyncio.sleep(random.uniform(0.1, 1.5))
        lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        has_lock = False

        for attempt in range(30):
            try:
                lock_socket.bind(('127.0.0.1', 9223))
                has_lock = True
                break
            except OSError:
                if attempt > 0 and attempt % 3 == 0:
                    if await _try_cdp_connect():
                        try:
                            lock_socket.close()
                        except Exception:
                            pass
                        return
                await asyncio.sleep(1.0)

        if not has_lock:
            if await _try_cdp_connect():
                return
            self._log("Não foi possível obter o lock do browser. Abortando init_browser.", "warning")
            return

        try:
            if self.playwright is None:
                self.playwright = await async_playwright().start()

            if await _try_cdp_connect():
                return

            molty_cfg = get_config()
            is_headless = molty_cfg.get("browser", {}).get("headless", True)

            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=os.path.join(MOLTY_DIR, 'browser_profile'),
                headless=is_headless,
                ignore_default_args=["--enable-automation"],
                args=[
                    '--remote-debugging-port=9222',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-infobars',
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-extensions',
                    '--window-position=0,0'
                ],
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0",
                viewport={"width": 1366, "height": 768},
                locale='pt-BR',
                timezone_id='America/Sao_Paulo',
                color_scheme='dark'
            )

            self.browser = self.context.browser
            await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()

            try:
                from playwright_stealth import Stealth
                await Stealth().apply_stealth_async(self.context)
                self._log("[Stealth] Anti-Bot Mode Ativado no Browser Principal (Master)!", "info")
            except ImportError:
                pass

            self._log("Navegador Master Inicializado na Porta 9222!", "info")
            await asyncio.sleep(2.0)
        except Exception as e:
            self._log(f"Erro ao iniciar navegador: {e}", "error")
        finally:
            if has_lock:
                try:
                    lock_socket.close()
                except Exception:
                    pass

    async def run_action(self, action: str, param: str) -> str:
        if action == "OPEN_BROWSER":
            await self.init()
            return "Navegador (re)inicializado com sucesso! Agora você pode usar GOTO, CLICK, etc."

        if not self.page or self.page.is_closed():
            return "Erro: O navegador está fechado ou não foi iniciado. Use a ferramenta OPEN_BROWSER primeiro!"

        try:
            if action != "INSPECT_PAGE":
                try:
                    await self.page.evaluate("document.querySelectorAll('.molty-visual-marker').forEach(el => el.remove())")
                except Exception:
                    pass

            if action == "GOTO":
                await self.page.goto(param, timeout=30000)
                await self.page.wait_for_load_state('domcontentloaded')
                title = await self.page.title()
                return f"Página carregada com sucesso. Título da Guia: {title}"

            elif action == "CLICK":
                await self.page.click(param, timeout=10000)
                await self.page.wait_for_timeout(2000)
                return f"Clique efetuado com sucesso no elemento: {param}"

            elif action == "TYPE":
                parts = param.split("|", 1)
                if len(parts) != 2:
                    return "Erro: Formato inválido para TYPE. Use [TYPE: seletor | texto]"
                selector = parts[0].strip()
                text = parts[1].strip()
                await self.page.fill(selector, text, timeout=10000)
                return f"Texto '{text}' digitado com sucesso no alvo '{selector}'"

            elif action == "PRESS_ENTER":
                await self.page.keyboard.press("Enter")
                await self.page.wait_for_timeout(2000)
                return "Tecla 'Enter' pressionada com sucesso!"

            elif action == "PRESS_KEY":
                await self.page.keyboard.press(param)
                await self.page.wait_for_timeout(1000)
                return f"Tecla '{param}' pressionada!"

            elif action == "READ_PAGE":
                content = await self.page.evaluate("document.body.innerText")
                return f"CONTEÚDO TEXTUAL DA PÁGINA ATUAL (truncado): {content[:4000]}"

            elif action == "INSPECT_PAGE":
                js_code = """() => {
                    try {
                        document.querySelectorAll('[data-operant-id]').forEach(el => el.removeAttribute('data-operant-id'));
                        document.querySelectorAll('.molty-visual-marker').forEach(el => el.remove());

                        const isVisible = (el) => {
                            const rect = el.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0 && 
                                   rect.top >= 0 && rect.top <= window.innerHeight &&
                                   rect.left >= 0 && rect.left <= window.innerWidth &&
                                   window.getComputedStyle(el).visibility !== 'hidden' &&
                                   window.getComputedStyle(el).display !== 'none';
                        };

                        const interactiveSelectors = [
                            'a', 'button', 'input', 'select', 'textarea', 
                            '[role="button"]', '[role="link"]', '[role="checkbox"]', 
                            '[role="tab"]', '[role="textbox"]', '[onclick]', '[contenteditable="true"]'
                        ];

                        const elements = Array.from(document.querySelectorAll(interactiveSelectors.join(',')))
                            .filter(isVisible)
                            .slice(0, 80);

                        let result = [];
                        elements.forEach((el, index) => {
                            const id = index + 1;
                            el.setAttribute('data-operant-id', id);
                            const rect = el.getBoundingClientRect();

                            const marker = document.createElement('div');
                            marker.className = 'molty-visual-marker';
                            Object.assign(marker.style, {
                                position: 'fixed',
                                left: rect.left + 'px',
                                top: rect.top + 'px',
                                width: rect.width + 'px',
                                height: rect.height + 'px',
                                border: '2px solid #38bdf8',
                                backgroundColor: 'rgba(56, 189, 248, 0.15)',
                                pointerEvents: 'none',
                                zIndex: '2147483647',
                                borderRadius: '3px',
                                boxSizing: 'border-box',
                                transition: 'all 0.2s ease'
                            });

                            const label = document.createElement('div');
                            label.innerText = id;
                            Object.assign(label.style, {
                                position: 'absolute',
                                top: '-12px',
                                left: '-12px',
                                background: '#38bdf8',
                                color: '#000',
                                fontSize: '11px',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                fontWeight: 'bold',
                                boxShadow: '0 2px 5px rgba(0,0,0,0.4)',
                                border: '1px solid #fff'
                            });
                            marker.appendChild(label);
                            document.body.appendChild(marker);

                            const tag = el.tagName.toLowerCase();
                            const role = el.getAttribute('role') || el.type || tag;
                            let text = (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').replace(/\\n/g, ' ').trim().substring(0, 60);

                            if (!text && tag !== 'input') text = "vazio/ícone";

                            result.push(`[data-operant-id="${id}"] -> <${tag} role="${role}"> ${text}`);
                        });
                        return result.join('\\n');
                    } catch (e) { return "Erro no script: " + e.message; }
                }"""
                content = await self.page.evaluate(js_code)
                return f"🔍 ELEMENTOS INTERATIVOS VISÍVEIS (Marcadores Azuis desenhados na tela! Use os seletores [data-operant-id=\"X\"] para CLICK/TYPE):\n{content}"

            elif action == "SCREENSHOT":
                temp_dir = os.path.join(self.base_dir, "temp")
                os.makedirs(temp_dir, exist_ok=True)
                filename = f"screenshot_{int(time.time())}.png"
                path_str = os.path.join(temp_dir, filename)
                await self.page.screenshot(path=path_str, full_page=False)
                return f"Screenshot capturado com sucesso. Se o usuário pediu a imagem, você DEVE dizer essa exata frase no meio do seu texto de volta para ele: [SCREENSHOT_TAKEN: {filename}]"

            elif action == "SCROLL_DOWN":
                await self.page.mouse.wheel(0, 600)
                await self.page.wait_for_timeout(1000)
                return "Página rolada para baixo com sucesso!"

        except Exception as e:
            return f"Erro durante a execução da ferramenta '{action}': {e}"

        return f"Ação desconhecida do navegador: {action}"
