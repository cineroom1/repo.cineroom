import xbmcgui
import xbmcaddon

ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
ADDON_PATH = xbmcaddon.Addon(id=ADDON_ID).getAddonInfo('path')
TELEGRAM_IMAGE = f"{ADDON_PATH}/resources/images/telegram.jpg"

class TelegramDialog(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.getControl(100).setImage(TELEGRAM_IMAGE)
        self.getControl(101).setLabel('[COLOR yellow]Acesse nosso grupo no Telegram![/COLOR]\n[COLOR white]Escaneie o QR Code ou procure por:[/COLOR]\n\n[COLOR lime]t.me/Cineroom1[/COLOR]')

    def onAction(self, action):
        if action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()
