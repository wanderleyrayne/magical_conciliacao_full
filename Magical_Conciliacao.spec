# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('assets', 'assets'), ('core', 'core'), ('database', 'database'), ('ui', 'ui'), ('utils', 'utils')]
hiddenimports = ['openpyxl', 'et_xmlfile', 'openpyxl.cell._writer', 'rapidfuzz', 'rapidfuzz.fuzz', 'rapidfuzz.process', 'requests', 'numpy', 'numpy.core']
datas += collect_data_files('openpyxl')
hiddenimports += collect_submodules('pandas')
hiddenimports += collect_submodules('openpyxl')
hiddenimports += collect_submodules('numpy')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Magical_Conciliacao',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Magical_Conciliacao',
)
