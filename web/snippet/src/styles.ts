/**
 * The widget's stylesheet — lives entirely INSIDE the shadow root.
 *
 * TRANSCRIBED, not redesigned: the values come from design/mockups/snippet/barber-widget.js, which is
 * the approved Cream & Ink interior locked in the design round. Two deliberate differences:
 *   1. font families are NAMESPACED (see fonts.ts) — the faces are injected at document level, so an
 *      un-namespaced "Fraunces" could collide with a family the host page already defines.
 *   2. the staged mock-conversation styles are gone: this widget talks to the real engine, and dead
 *      CSS for a conversation that no longer exists is exactly what code-style.md forbids.
 *
 * `:host{all:initial}` is the load-bearing line. The shadow boundary already blocks the host's
 * SELECTORS; `all:initial` cuts what selectors cannot reach — INHERITED properties (font-family,
 * line-height, color, box-sizing…) flowing down from <body>. Everything the widget needs is therefore
 * re-declared below; nothing may be assumed.
 */
import { FONT_DISPLAY, FONT_UI } from './fonts';

export const STYLES = `
:host{all:initial}
:host{--cream:#F1EEE6;--ink:#16150F;--oxide:#B4472E;--oxide-soft:#D98B66;--muted:#5C594E;--stamp:#C9C4B4;
--frame:rgba(22,21,15,.35);--edge:rgba(22,21,15,.25);--ease:cubic-bezier(.22,.61,.36,1);
--font-display:${FONT_DISPLAY};--font-ui:${FONT_UI}}
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}

/* z-index: the classic overlay ceiling, so an ambitious host header cannot cover the launcher. */
.launcher{position:fixed;right:26px;bottom:24px;z-index:2147483000;display:inline-flex;align-items:center;gap:10px;
background:var(--ink);color:var(--cream);border:none;cursor:pointer;border-radius:999px;
font-family:var(--font-ui);font-size:14.5px;font-weight:600;padding:14px 24px;
box-shadow:0 16px 38px -14px rgba(22,21,15,.55);transition:transform .3s var(--ease)}
.launcher:hover{transform:translateY(-2px)}
.launcher:active{transform:scale(.97)}
.launcher:focus-visible,.panel-close:focus-visible,.composer-input:focus-visible,.composer-send:focus-visible{outline:2px solid var(--oxide);outline-offset:3px}
.online-dot{width:8px;height:8px;border-radius:50%;background:var(--oxide-soft);display:inline-block;flex-shrink:0}
.panel .online-dot{width:7px;height:7px;background:var(--oxide)}

.panel{position:fixed;right:26px;bottom:88px;z-index:2147483000;width:390px;max-width:calc(100vw - 32px);
background:var(--cream);border:1.5px solid var(--ink);border-radius:6px;
box-shadow:8px 8px 0 rgba(22,21,15,.12),0 30px 60px -30px rgba(22,21,15,.5);overflow:hidden;
display:flex;flex-direction:column;transform-origin:bottom right;
font-family:var(--font-ui);font-size:16px;line-height:1.6;color:var(--ink);-webkit-font-smoothing:antialiased}
.panel:not(.is-open){display:none}
.panel.is-open{animation:panelin .32s var(--ease) both}
@keyframes panelin{from{opacity:0;transform:translateY(14px) scale(.98)}to{opacity:1;transform:none}}

.panel-head{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid var(--frame)}
.panel-avatar{width:38px;height:38px;border-radius:50%;background:var(--ink);color:var(--cream);display:flex;
align-items:center;justify-content:center;font-family:var(--font-display);font-weight:600;font-size:14px;flex-shrink:0}
.panel-id{line-height:1.35;flex:1;min-width:0}
.panel-name{display:block;font-family:var(--font-display);font-weight:600;font-size:16px;letter-spacing:-.01em}
.panel-status{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:6px}
.demo-tag{flex-shrink:0;font-family:var(--font-ui);font-size:10px;font-weight:700;letter-spacing:.1em;
text-transform:uppercase;color:var(--oxide);border:1px solid var(--oxide);border-radius:4px;padding:2px 6px}
.panel-close{width:30px;height:30px;border-radius:50%;font-size:19px;line-height:1;color:var(--muted);flex-shrink:0;
display:flex;align-items:center;justify-content:center;background:none;border:none;cursor:pointer;font-family:var(--font-ui);
transition:background .15s var(--ease),color .15s var(--ease)}
.panel-close:hover{background:rgba(22,21,15,.08);color:var(--ink)}

.thread{padding:18px;display:flex;flex-direction:column;gap:12px;max-height:min(60vh,440px);overflow-y:auto}
.msg{max-width:88%;padding:11px 15px;font-size:14.5px;line-height:1.5}
.msg.user{align-self:flex-end;max-width:84%;background:var(--ink);color:var(--cream);border-radius:16px 16px 4px 16px}
.msg.bot{align-self:flex-start;background:#FFF;border:1px solid var(--edge);border-radius:16px 16px 16px 4px}
/* The transport layer speaking (timeout, offline, blocked) — never dressed as the shop's voice. */
.msg.system{align-self:center;max-width:94%;background:transparent;border:1px dashed var(--edge);color:var(--muted);
border-radius:10px;font-size:13px;text-align:center}
.stamp{display:block;font-size:10.5px;margin-top:5px;color:var(--muted)}
.msg.system .retry{display:inline-block;margin-top:8px;font-family:var(--font-ui);font-size:12.5px;
font-weight:600;color:var(--ink);background:transparent;border:1px solid var(--edge);border-radius:999px;
padding:5px 12px;cursor:pointer}
.msg.system .retry:hover{background:rgba(22,21,15,.06)}
.msg.system .retry:focus-visible{outline:2px solid var(--oxide);outline-offset:2px}
.msg.user .stamp{color:var(--stamp)}

.typing{align-self:flex-start;display:flex;gap:5px;background:#FFF;border:1px solid var(--edge);
border-radius:16px 16px 16px 4px;padding:12px 15px}
.typing i{width:6px;height:6px;border-radius:50%;background:var(--muted);display:block;animation:dotb 1.1s infinite}
.typing i:nth-child(2){animation-delay:.15s}
.typing i:nth-child(3){animation-delay:.3s}
@keyframes dotb{0%,60%,100%{transform:translateY(0);opacity:.45}30%{transform:translateY(-4px);opacity:1}}

/* S3 — Cloudflare draws its own widget here. In Invisible mode it stays empty and zero-height, which is
   why the slot must never be display:none: a hidden container is not a challenge a visitor could solve. */
.turnstile-slot{padding:0 18px}
.turnstile-slot:empty{padding:0}

.composer{display:flex;align-items:center;gap:10px;padding:13px 18px;border-top:1px solid var(--frame)}
.composer-input{flex:1;font-family:var(--font-ui);font-size:14px;color:var(--ink);background:#FFF;
border:1px solid var(--edge);border-radius:999px;padding:10px 16px;min-width:0}
.composer-input::placeholder{color:var(--muted)}
.composer-input:disabled{background:rgba(22,21,15,.04);color:var(--muted)}
.composer-send{width:38px;height:38px;border-radius:50%;background:var(--ink);color:var(--cream);font-size:16px;
display:flex;align-items:center;justify-content:center;flex-shrink:0;border:none;cursor:pointer;font-family:var(--font-ui)}
.composer-send:disabled{opacity:.45;cursor:default}

@media (max-width:480px){.panel{left:12px;right:12px;bottom:82px;width:auto;max-width:none}.thread{max-height:52vh}}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none !important;transition:none !important}}
`;
