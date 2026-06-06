import os
import logging
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger("CryptoHelper")

def ensure_directory_exists(file_path: str):
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

def generate_ephemeral_rsa_key() -> rsa.RSAPrivateKey:
    """Generates an ephemeral RSA private key in memory."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

def ensure_test_credentials(cert_path: str, key_path: str, ca_path: str = None, dev_mode: bool = False):
    """
    Checks if mTLS certificate files exist.
    If they do not exist, generates a self-signed testing cert and key on-the-fly (if dev_mode=True).
    Otherwise, raises FileNotFoundError.
    """
    if os.path.exists(cert_path) and os.path.exists(key_path):
        logger.info(f"Using existing certificates: {cert_path}, {key_path}")
        return

    if not dev_mode:
        raise FileNotFoundError(
            f"mTLS certificates '{cert_path}' or '{key_path}' not found, and auto-generation is disabled "
            f"because dev_mode is false. Please mount/provide certificates."
        )

    logger.warning(f"Certificates '{cert_path}' or '{key_path}' not found. Generating self-signed mock credentials for testing...")
    
    ensure_directory_exists(cert_path)
    ensure_directory_exists(key_path)

    private_key = generate_ephemeral_rsa_key()
    
    # Create self-signed identity
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"TW"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Taipei"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Thaumio Digital Twin"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])

    now = datetime.now(timezone.utc)
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        now - timedelta(days=1)
    ).not_valid_after(
        now + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
        critical=False,
    ).sign(private_key, hashes.SHA256())

    # Write private key
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # Write mock CA certificate if configured
    if ca_path:
        ensure_directory_exists(ca_path)
        with open(ca_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Mock certificates generated successfully at: cert_path={cert_path}, key_path={key_path}")
