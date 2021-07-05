from bot import aria2, download_dict_lock, STOP_DUPLICATE_MIRROR, TORRENT_DIRECT_LIMIT, TAR_UNZIP_LIMIT
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.bot_utils import *
from .download_helper import DownloadHelper
from bot.helper.mirror_utils.status_utils.aria_download_status import AriaDownloadStatus
from bot.helper.telegram_helper.message_utils import *
import threading
from aria2p import API
from time import sleep
 
 
class AriaDownloadHelper(DownloadHelper):
 
    def __init__(self):
        super().__init__()
 
    @new_thread
    def __onDownloadStarted(self, api, gid):
        if STOP_DUPLICATE_MIRROR or TORRENT_DIRECT_LIMIT is not None or TAR_UNZIP_LIMIT is not None:
            sleep(0.5)
            dl = getDownloadByGid(gid)
            download = api.get_download(gid)
            
            if STOP_DUPLICATE_MIRROR:
                LOGGER.info(f"Checking File/Folder if already in Drive...")
                self.name = download.name
                sname = download.name
                if self.listener.isTar:
                    sname = sname + ".tar"
                if self.listener.extract:
                    smsg = None
                else:
                    gdrive = GoogleDriveHelper(None)
                    smsg, button = gdrive.drive_list(sname)
                if smsg:
                    dl.getListener().onDownloadError(f'File is already available in Drive.😡\n\n📒 Must Search Files! Before Mirroring')
                    aria2.remove([download])
                    sendMarkup("Here are the search results:", dl.getListener().bot, dl.getListener().update, button)
                    return
 
            if TORRENT_DIRECT_LIMIT is not None or TAR_UNZIP_LIMIT is not None:
                limit = None
                if TAR_UNZIP_LIMIT is not None and (self.listener.isTar or self.listener.extract):
                    LOGGER.info(f"Checking File/Folder Size...")
                    limit = TAR_UNZIP_LIMIT
                    mssg = f'Tar/Unzip limit is {TAR_UNZIP_LIMIT}'
                elif TORRENT_DIRECT_LIMIT is not None and limit is None:
                    LOGGER.info(f"Checking File/Folder Size...")
                    limit = TORRENT_DIRECT_LIMIT
                    mssg = f'Torrent/Direct limit is {TORRENT_DIRECT_LIMIT}'
                if limit is not None:
                    sleep(1.5)
                    size = aria2.get_download(gid).total_length
                    limit = limit.split(' ', maxsplit=1)
                    limitint = int(limit[0])
                    if 'G' in limit[1] or 'g' in limit[1]:
                        if size > limitint * 1024**3:
                            dl.getListener().onDownloadError(f'📀 𝗙𝗶𝗹𝗲 𝗦𝗶𝘇𝗲:\n➩ 〘{get_readable_file_size(size)}〙\n\n🏷️ 𝗠𝗶𝗿𝗿𝗼𝗿 𝗟𝗶𝗺𝗶𝘁: 〘{TORRENT_DIRECT_LIMIT}〙')
                            aria2.remove([download])
                            return
                    elif 'T' in limit[1] or 't' in limit[1]:
                        if size > limitint * 1024**4:
                            dl.getListener().onDownloadError(f'📀 𝗙𝗶𝗹𝗲 𝗦𝗶𝘇𝗲:\n➩ 〘{get_readable_file_size(size)}〙\n\n🏷️ 𝗠𝗶𝗿𝗿𝗼𝗿 𝗟𝗶𝗺𝗶𝘁: 〘{TORRENT_DIRECT_LIMIT}〙')
                            aria2.remove([download])
                            return
        update_all_messages()
 
    def __onDownloadComplete(self, api: API, gid):
        LOGGER.info(f"onDownloadComplete: {gid}")
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        if download.followed_by_ids:
            new_gid = download.followed_by_ids[0]
            new_download = api.get_download(new_gid)
            with download_dict_lock:
                sleep(1)
                download_dict[dl.uid()] = AriaDownloadStatus(new_gid, dl.getListener())
                if new_download.is_torrent:
                    download_dict[dl.uid()].is_torrent = True
            update_all_messages()
            LOGGER.info(f'Changed gid from {gid} to {new_gid}')
        else:
            if dl:
                threading.Thread(target=dl.getListener().onDownloadComplete).start()
  
    @new_thread
    def __onDownloadStopped(self, api, gid):
        sleep(0.5)
        dl = getDownloadByGid(gid)
        if dl: 
            dl.getListener().onDownloadError('𝘠𝘰𝘶𝘳 𝘛𝘰𝘳𝘳𝘦𝘯𝘵 𝘪𝘴 𝘋𝘦𝘢𝘥.\n\n★ There is no SEED in the link you provided\n\n⛔ 𝑷𝒍𝒆𝒂𝒔𝒆 𝒄𝒉𝒆𝒄𝒌 𝒚𝒐𝒖𝒓 𝒍𝒊𝒏𝒌! 𝑩𝒆𝒇𝒐𝒓𝒆 𝑴𝒊𝒓𝒓𝒐𝒓')
 
    @new_thread
    def __onDownloadError(self, api, gid):
        sleep(0.5)  # sleep for split second to ensure proper dl gid update from onDownloadComplete
        dl = getDownloadByGid(gid)
        download = api.get_download(gid)
        error = download.error_message
        LOGGER.info(f"Download Error: {error}")
        if dl: 
            dl.getListener().onDownloadError(error)
 
    def start_listener(self):
        aria2.listen_to_notifications(threaded=True, on_download_start=self.__onDownloadStarted,
                                      on_download_error=self.__onDownloadError,
                                      on_download_stop=self.__onDownloadStopped,
                                      on_download_complete=self.__onDownloadComplete)
 
    def add_download(self, link: str, path, listener, filename):
        if is_magnet(link):
            download = aria2.add_magnet(link, {'dir': path, 'out': filename})
        else:
            download = aria2.add_uris([link], {'dir': path, 'out': filename})
        if download.error_message:  # no need to proceed further at this point
            listener.onDownloadError(download.error_message)
            return
        with download_dict_lock:
            download_dict[listener.uid] = AriaDownloadStatus(download.gid, listener)
            LOGGER.info(f"Started: {download.gid} DIR:{download.dir} ")
        self.listener = listener
