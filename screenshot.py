"""Gera um screenshot SVG da TUI para inspeção visual (sem terminal real).

    python screenshot.py [seed] [cena]

Cenas: explore (padrão) · lockdown · boot · pause · contrast · desk · shop · tutorial
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from coldboot.app import ColdBootApp


async def main(seed, scene):
    # Os previews nunca tocam no ~/.coldboot de quem roda.
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        # O tutorial só aparece na cena 'tutorial'; o resto começa no jogo.
        app = ColdBootApp(seed=seed, boot=(scene == "boot"),
                          tutorial_on=(scene == "tutorial"),
                          save_path=tmp / "save.json", settings_path=tmp / "cfg.json")
        async with app.run_test(size=(110, 34)) as pilot:
            await pilot.pause()

            if scene == "boot":
                await pilot.pause(3.2)       # pega o POST no meio da barra de carga
            elif scene == "tutorial":
                await pilot.pause(1.0)
            else:
                if scene == "contrast":
                    app.settings.high_contrast = True
                    app.apply_settings()
                # Um rig montado deixa o HUD e a mesa mais interessantes.
                app.state.wallet = 6000.0
                for pid in ["mb_c3", "cpu_s3", "ram_d5_32", "psu_850", "cool_fans",
                            "net_husky", "gpu_a", "gpu_b"]:
                    from coldboot import economy
                    economy.buy(app.state, pid)
                app.state.wallet = 420.0
                app.state.processes.append("miner")
                app._apply_rig()
                for cmd in ["scan", "cd /users", "ls", "look terminal"]:
                    app.query_one("#prompt").value = cmd
                    await pilot.press("enter")
                    await pilot.pause(0.2)
                app.refresh_status()
                app.refresh_rig()
                if scene == "lockdown":
                    app.state.trace = 100.0
                    app._check_trace()
                    await pilot.pause(1.5)
                await pilot.pause(1.5)
                if scene == "pause":
                    await pilot.press("escape")
                    await pilot.pause(0.4)
                elif scene == "desk":
                    app.state.sector = 3      # como se tivesse acabado de limpar o 2
                    app.go_desk("clear")
                    await pilot.pause(0.4)
                elif scene == "shop":
                    app.query_one("#prompt").value = "store"
                    await pilot.press("enter")
                    await pilot.pause(0.4)

            out = f"preview_{scene}.svg"
            with open(out, "w", encoding="utf-8") as f:
                f.write(app.export_screenshot(
                    title=f"Project: COLD-BOOT  (seed {app.state.seed})"))
        print(f"{out} gerado (seed {app.state.seed}, cena {scene})")


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else None
    scene = sys.argv[2] if len(sys.argv) > 2 else "explore"
    asyncio.run(main(seed, scene))
