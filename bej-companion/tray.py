"""Windows-only tray controls. No device capture or external messaging."""
import os
import threading


def start_tray(open_workspace, pause_reminders, quit_service):
    if os.name != 'nt':
        return None
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new('RGB', (64, 64), '#235e44')
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype('segoeuib.ttf', 46)
    except OSError:
        font = ImageFont.load_default(size=46)
    draw.text((32, 29), 'b', font=font, fill='#f5f7f4', anchor='mm')
    def quit_icon(icon, _item):
        quit_service()
        icon.stop()
    icon = pystray.Icon('BejSecretary', image, 'Bej Secretary · local assistant', menu=pystray.Menu(
        pystray.MenuItem('Open Bej', lambda *_: open_workspace(), default=True),
        pystray.MenuItem('Pause all reminders', lambda *_: pause_reminders()),
        pystray.MenuItem('Quit Bej', quit_icon),
    ))
    threading.Thread(target=icon.run, name='bej-tray', daemon=True).start()
    return icon
