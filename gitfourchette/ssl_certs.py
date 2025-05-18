#!/usr/bin/env python3
# -----------------------------------------------------------------------------
# Copyright (C) 2025 Iliyas Jorio.
# This file is part of GitFourchette, distributed under the GNU GPL v3.
# For full terms, see the included LICENSE file.
# -----------------------------------------------------------------------------

"""
This module needs to be imported as early as possible, before pygit2 is loaded.
It configures SSL certificates for pygit2, which is required for HTTPS operations.
"""

import os
import sys
import logging

def configure_ssl_certificates():
    """Configure SSL certificates for pygit2"""
    # Common certificate directories
    cert_dirs = [
        '/etc/ssl/certs',
        '/etc/pki/tls/certs',
        '/etc/pki/ca-trust/extracted/pem',
        '/usr/share/ca-certificates'
    ]
    
    # Common certificate files
    cert_files = [
        '/etc/ssl/certs/ca-certificates.crt',
        '/etc/pki/tls/certs/ca-bundle.crt',
        '/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem'
    ]

    # Check if certificates are already configured
    if os.environ.get('SSL_CERT_DIR') and os.environ.get('SSL_CERT_FILE'):
        logging.debug(f"SSL certificates already configured: DIR={os.environ['SSL_CERT_DIR']}, FILE={os.environ['SSL_CERT_FILE']}")
        return True
    
    # Try to find certificate directory on the system
    for cert_dir in cert_dirs:
        if os.path.isdir(cert_dir):
            os.environ['SSL_CERT_DIR'] = cert_dir
            logging.debug(f"Using SSL certificate directory: {cert_dir}")
            break
    
    # Try to find certificate file on the system
    for cert_file in cert_files:
        if os.path.isfile(cert_file):
            os.environ['SSL_CERT_FILE'] = cert_file
            logging.debug(f"Using SSL certificate file: {cert_file}")
            break
    
    # Check if configuration was successful
    if not os.environ.get('SSL_CERT_DIR') or not os.environ.get('SSL_CERT_FILE'):
        logging.warning("Could not find SSL certificates!")
        return False
        
    return True

# Configure SSL certificates when this module is imported
configure_ssl_certificates() 