from asyncssh import PermissionDenied, SFTPClient, SFTPName, SFTPNoSuchFile, SSHClientConnection
from fastapi import APIRouter, Form, status, WebSocket, WebSocketDisconnect

from datetime import datetime
from os.path import join
from typing import Optional

from config import DATA_DIR
from schemas.user import User
from schemas.listdir import ListDir
from utils import get_ssh_session

from ..depends import user_depends
from ..exceptions import AUTHORIZE_FAIL, FILE_NOT_FOUND, FILE_OVERSIZE, UNKNOW_ERROR
from ..validator import get_user

def __ls_filter(item: SFTPName, uid: int, file_or_dir: int=1) -> bool:
    if item.attrs.type != file_or_dir:
        return False
    elif item.attrs.uid == uid and bool(item.attrs.permissions & 1 << 8):
        return True
    return bool(item.attrs.permissions & 1 << 2)

async def listdir(
    sftp: SFTPClient,
    uid: int,
    path: str="."
) -> ListDir:
    ls = list(await sftp.readdir(path))
    ls.sort(key=lambda item: item.filename)
    files=list(map(lambda item: item.filename, filter(
        lambda item: __ls_filter(item, uid, 1),
        ls
    )))
    directory=list(map(lambda item: item.filename, filter(
        lambda item: __ls_filter(item, uid, 2),
        ls
    )))
    result = ListDir(
        path=path,
        files=files,
        directory=directory,
    )
    return result

router = APIRouter(
    prefix="/pull",
    tags=["Pull"]
)
@router.websocket("/explorer")
async def explorer_websocket(
    ws: WebSocket,
    token: str
):
    client: Optional[SSHClientConnection] = None
    user: User = await get_user(token)
    try:
        client = await get_ssh_session(
            username=user.username,
            password=user.decrypted_password()
        )
        sftp = await client.start_sftp_client()
        uid = int((await client.run("echo $UID")).stdout)

        await ws.accept()
        path = await sftp.realpath(f".")
        while True:
            result = await listdir(sftp, uid, path)
            await ws.send_json(result.model_dump())
            try:
                selected = await ws.receive_text()
                new_path = await sftp.realpath(f"{path}/{selected}")
                isdir = await sftp.isdir(new_path)
                if isdir:
                    path = new_path
            except SFTPNoSuchFile:
                pass
    except WebSocketDisconnect:
        pass
    except PermissionDenied:
        raise AUTHORIZE_FAIL
    except:
        raise UNKNOW_ERROR
    finally:
        if client:
            client.close()

@router.post(
    path="",
    status_code=status.HTTP_201_CREATED
)
async def pull(
    path: str = Form(),
    user: User = user_depends
) -> str:
    try:
        client = await get_ssh_session(
            username=user.username,
            password=user.decrypted_password()
        )
        sftp = await client.start_sftp_client()
        isfile = await sftp.isfile(path)
        if not isfile:
            raise FILE_NOT_FOUND
        filesize = await sftp.getsize(path)
        if filesize > 32 * 1024:
            raise FILE_OVERSIZE
        
        user_hash = user.hash_value()

        timestamp = datetime.now().strftime("%Y_%m_%dT%H.%M.%S")
        file_name = f"{user_hash}-{timestamp}-{path.rsplit('/', 1)[1]}"

        await sftp.get(path, join(DATA_DIR, file_name))
        
        return file_name
    except PermissionDenied:
        raise AUTHORIZE_FAIL
    except:
        raise UNKNOW_ERROR
    finally:
        if client:
            client.close()