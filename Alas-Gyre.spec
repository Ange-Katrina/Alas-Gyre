# -*- mode: python ; coding: utf-8 -*-

import os

from PyInstaller.configure import _check_upx_availability
from PyInstaller.config import CONF


LOCAL_UPX_DIR = os.path.abspath(os.path.join('tools', 'upx-5.1.1-win64'))
if os.path.exists(os.path.join(LOCAL_UPX_DIR, 'upx.exe')):
    CONF['upx_dir'] = LOCAL_UPX_DIR
    CONF['upx_available'] = _check_upx_availability(LOCAL_UPX_DIR)


EXCLUDED_QT_BINARIES = {
    # QWidget app; these are pulled by broad PySide6 hooks/plugins but are not used.
    'pyside6\\opengl32sw.dll',
    'pyside6\\qt6network.dll',
    'pyside6\\qtnetwork.pyd',
    'pyside6\\qt6opengl.dll',
    'pyside6\\qt6pdf.dll',
    'pyside6\\qt6qml.dll',
    'pyside6\\qt6qmlmeta.dll',
    'pyside6\\qt6qmlmodels.dll',
    'pyside6\\qt6qmlworkerscript.dll',
    'pyside6\\qt6quick.dll',
    'pyside6\\qt6svg.dll',
    'pyside6\\qt6virtualkeyboard.dll',
}


def _normalized_toc_name(entry):
    return entry[0].replace('/', '\\').lower()


def _keep_binary(entry):
    name = _normalized_toc_name(entry)
    if name in EXCLUDED_QT_BINARIES:
        return False
    if name.startswith('pyside6\\plugins\\platforms\\'):
        return name.endswith('\\qwindows.dll')
    if name.startswith('pyside6\\plugins\\imageformats\\'):
        return name.endswith('\\qico.dll') or name.endswith('\\qjpeg.dll')
    if name.startswith('pyside6\\plugins\\iconengines\\'):
        return False
    if name.startswith('pyside6\\plugins\\platforminputcontexts\\'):
        return False
    if name.startswith('pyside6\\plugins\\generic\\'):
        return False
    if name.startswith('pyside6\\plugins\\networkinformation\\'):
        return False
    if name.startswith('pyside6\\plugins\\tls\\'):
        return False
    return True


def _keep_data(entry):
    name = _normalized_toc_name(entry)
    if name.startswith('pyside6\\translations\\'):
        return False
    return True

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ui/style.qss', 'ui'),
        ('ui/light.qss', 'ui'),
        ('ui/assets/alas.ico', 'ui/assets'),
        ('ui/assets/bottom_icons/settings.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/settings_hover.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/home.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/home_hover.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/float.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/float_hover.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/log.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/log_hover.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/screenshot.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/screenshot_hover.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/delete.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/delete_hover.png', 'ui/assets/bottom_icons'),
        ('ui/assets/bottom_icons/delete_disabled.png', 'ui/assets/bottom_icons'),
        ('resources/start_gyre_alas.bat.template', 'resources'),
        ('resources/start_gyre_alas.sh.template', 'resources'),
        ('resources/gyre_runtime_updater.py', 'resources'),
        ('overlay/sitecustomize.py', 'overlay'),
        ('overlay/gyre_overlay_runtime.py', 'overlay'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'OpenSSL',
        'cryptography',
        'urllib3.contrib.pyopenssl',
        'PySide6.QtNetwork',
        'PySide6.QtOpenGL',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtVirtualKeyboard',
    ],
    noarchive=False,
    optimize=0,
)

a.binaries = [entry for entry in a.binaries if _keep_binary(entry)]
a.datas = [entry for entry in a.datas if _keep_data(entry)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Alas-Gyre',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=['python3.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='ui/assets/alas.ico'
)
