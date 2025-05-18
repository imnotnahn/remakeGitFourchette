#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Copyright (C) 2025 Iliyas Jorio.
# This file is part of GitFourchette, distributed under the GNU GPL v3.
# For full terms, see the included LICENSE file.
# -----------------------------------------------------------------------------

"""
Hỗ trợ xác thực Git cho pygit2
Module này đảm bảo rằng xác thực Git hoạt động đúng cách.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

def configure_git_auth():
    """Cấu hình xác thực Git"""
    # Đảm bảo HOME được đặt đúng
    if not os.environ.get('HOME'):
        os.environ['HOME'] = str(Path.home())
        logging.debug(f"Đã thiết lập biến môi trường HOME thành {os.environ['HOME']}")
    
    # Đảm bảo Git credential helper được cấu hình
    try:
        subprocess.run(
            ['git', 'config', '--global', 'credential.helper', 'store'],
            check=True,
            capture_output=True,
            text=True
        )
        logging.debug("Đã cấu hình Git credential.helper thành 'store'")
    except Exception as e:
        logging.warning(f"Không thể cấu hình Git credential helper: {e}")
    
    # Đảm bảo chế độ tương tác được bật
    try:
        subprocess.run(
            ['git', 'config', '--global', 'credential.interactive', 'always'],
            check=True, 
            capture_output=True,
            text=True
        )
        logging.debug("Đã thiết lập credential.interactive thành 'always'")
    except Exception as e:
        logging.warning(f"Không thể thiết lập credential.interactive: {e}")
    
    # Tạo file gitconfig nếu chưa có
    git_config_path = os.path.join(os.environ.get('HOME', str(Path.home())), '.gitconfig')
    if not os.path.exists(git_config_path):
        try:
            with open(git_config_path, 'w') as f:
                f.write("""[credential]
\thelper = store
\tinteractive = always
""")
            logging.debug(f"Đã tạo file {git_config_path}")
        except Exception as e:
            logging.warning(f"Không thể tạo file .gitconfig: {e}")
    
    # Kiểm tra và tạo thư mục ~/.git-credentials nếu cần
    git_credentials_path = os.path.join(os.environ.get('HOME', str(Path.home())), '.git-credentials')
    if not os.path.exists(git_credentials_path):
        try:
            with open(git_credentials_path, 'w') as f:
                pass  # Tạo file trống
            os.chmod(git_credentials_path, 0o600)  # Đặt quyền đọc/ghi cho chủ sở hữu
            logging.debug(f"Đã tạo file {git_credentials_path}")
        except Exception as e:
            logging.warning(f"Không thể tạo file .git-credentials: {e}")

# Cấu hình xác thực Git khi module được import
configure_git_auth() 