import datetime
from pathlib import Path

import typer
from asn1crypto import cms, core, pem, util, x509
from cryptography import x509 as crypto_x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa, utils
from rich.console import Console

from ..constants import CA_KEY, CA_PEM, DEV_PEM, REQUIRED_PRIVATE_KEY_PERMISSIONS

CHUNK_SIZE = 1024 * 1024


def generate_ca(
    console: Console, cert_dir: Path, subject: crypto_x509.Name, not_valid_after: datetime, passphrase=None
):
    ca_key_file_path = cert_dir / CA_KEY
    ca_cert_file_path = cert_dir / CA_PEM

    console.print("Generating CA...", style="bold blue")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_key_encryption = (
        serialization.BestAvailableEncryption(passphrase.encode()) if passphrase else serialization.NoEncryption()
    )

    ca_key_file_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=private_key_encryption,
        )
    )

    console.print(f"Wrote CA private key: {ca_key_file_path}", style="bold green")
    public_key = private_key.public_key()
    builder = crypto_x509.CertificateBuilder()
    builder = builder.subject_name(subject)
    builder = builder.issuer_name(subject)
    builder = builder.not_valid_before(datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=1))
    builder = builder.not_valid_after(not_valid_after)
    builder = builder.serial_number(crypto_x509.random_serial_number())
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        crypto_x509.BasicConstraints(ca=True, path_length=0),
        critical=False,
    )
    subject_identifier = crypto_x509.SubjectKeyIdentifier.from_public_key(public_key)
    builder = builder.add_extension(
        subject_identifier,
        critical=False,
    )
    builder = builder.add_extension(
        crypto_x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(subject_identifier),
        critical=False,
    )
    builder = builder.add_extension(
        crypto_x509.KeyUsage(
            digital_signature=False,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=True,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=False,
    )
    certificate = builder.sign(
        private_key=private_key,
        algorithm=hashes.SHA256(),
    )

    ca_cert_file_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    console.print(f"Wrote CA certificate: {ca_cert_file_path}", style="bold green")


def generate_dev_cert(
    console: Console,
    cert_dir: Path,
    subject: crypto_x509.Name,
    not_valid_after: datetime,
    ca_passphrase=None,
    dev_passphrase=None,
):
    ca_key_file_path = cert_dir / CA_KEY
    ca_cert_file_path = cert_dir / CA_PEM
    dev_cert_file_path = cert_dir / DEV_PEM

    console.print(f"Loading CA private key {ca_key_file_path.as_posix()}", style="bold blue")
    ca_private_key = serialization.load_pem_private_key(
        ca_key_file_path.read_bytes(),
        password=ca_passphrase.encode() if ca_passphrase else None,
        backend=default_backend,
    )

    console.print(f"Loading CA certificate {ca_cert_file_path.as_posix()}", style="bold blue")
    ca_cert = crypto_x509.load_pem_x509_certificate(ca_cert_file_path.read_bytes())

    if ca_cert.issuer == subject:
        console.print("Certificate subject must be different from its issuer, aborting!", style="bold red")
        raise typer.Exit(1)

    console.print("Generating developer certificate...", style="bold blue")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    private_key_encryption = (
        serialization.BestAvailableEncryption(dev_passphrase.encode())
        if dev_passphrase
        else serialization.NoEncryption()
    )

    public_key = private_key.public_key()

    builder = crypto_x509.CertificateBuilder()
    builder = builder.subject_name(subject)
    builder = builder.issuer_name(ca_cert.issuer)
    builder = builder.not_valid_before(datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(days=1))
    builder = builder.not_valid_after(not_valid_after)
    builder = builder.serial_number(crypto_x509.random_serial_number())
    builder = builder.public_key(public_key)
    builder = builder.add_extension(
        crypto_x509.SubjectKeyIdentifier.from_public_key(public_key),
        critical=False,
    )
    try:
        subject_identifier = ca_cert.extensions.get_extension_for_class(crypto_x509.SubjectKeyIdentifier)
        builder = builder.add_extension(
            crypto_x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(subject_identifier.value),
            critical=False,
        )
    except crypto_x509.ExtensionNotFound:
        pass
    builder = builder.add_extension(
        crypto_x509.KeyUsage(
            digital_signature=True,
            content_commitment=False,
            key_encipherment=False,
            data_encipherment=False,
            key_agreement=False,
            key_cert_sign=False,
            crl_sign=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=False,
    )
    certificate = builder.sign(
        private_key=ca_private_key,
        algorithm=hashes.SHA256(),
    )

    dev_cert_file_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))

    console.print(f"Wrote developer certificate: {dev_cert_file_path.as_posix()}", style="bold green")

    with dev_cert_file_path.open("ab") as fp:
        fp.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=private_key_encryption,
            )
        )

    console.print(f"Wrote developer private key: {dev_cert_file_path}", style="bold green")

    dev_cert_file_path.chmod(REQUIRED_PRIVATE_KEY_PERMISSIONS)


def sign_file(console: Console, file_path: Path, certificate_file_path: Path, dev_passphrase=None):

    console.print(f"Signing {file_path} using {certificate_file_path} certificate")

    private_key = serialization.load_pem_private_key(
        certificate_file_path.read_bytes(),
        password=dev_passphrase.encode() if dev_passphrase else None,
        backend=default_backend(),
    )

    sha256 = hashes.SHA256()
    hasher = hashes.Hash(sha256)

    with file_path.open("rb") as fp:
        while buf := fp.read(CHUNK_SIZE):
            hasher.update(buf)

    signature = private_key.sign(hasher.finalize(), padding.PKCS1v15(), utils.Prehashed(sha256))
    signed_data = cms.SignedData()
    signed_data["version"] = "v1"
    signed_data["encap_content_info"] = util.OrderedDict([("content_type", "data"), ("content", None)])
    signed_data["digest_algorithms"] = [util.OrderedDict([("algorithm", "sha256"), ("parameters", None)])]

    signer_info = cms.SignerInfo()
    signer_info["version"] = 1
    signer_info["digest_algorithm"] = util.OrderedDict([("algorithm", "sha256"), ("parameters", None)])
    signer_info["signature_algorithm"] = util.OrderedDict([("algorithm", "rsassa_pkcs1v15"), ("parameters", core.Null)])
    signer_info["signature"] = signature

    der_bytes = certificate_file_path.read_bytes()
    if pem.detect(der_bytes):
        _type_name, _headers, der_bytes = pem.unarmor(der_bytes)
    else:
        console.print("Wrong certificate format, expected PEM, aborting!", style="bold red")
        raise typer.Exit(1)

    cert = x509.Certificate.load(der_bytes)

    signed_data["certificates"] = [
        cert,
    ]

    try:
        signer_info["sid"] = cms.SignerIdentifier(
            {
                "issuer_and_serial_number": util.OrderedDict(
                    [
                        ("issuer", cert.issuer),
                        ("serial_number", cert.serial_number),
                    ]
                )
            }
        )
    except ValueError as e:
        # Error returned by asn1crypto if the fused cert/key has key before cert
        if (
            "Error parsing asn1crypto.x509.TbsCertificate - method should have been constructed,"
            " but primitive was found"
        ) in e.args[0]:

            console.print(
                (
                    "Error: Malformed fused certkey, certificate should be first;"
                    " please regenerate the certificate or reorder manually"
                ),
                style="bold red",
            )
            raise typer.Exit(1) from None
        else:
            raise

    signed_data["signer_infos"] = [
        signer_info,
    ]

    # dump  ASN.1 object
    asn1obj = cms.ContentInfo()
    asn1obj["content_type"] = "signed_data"
    asn1obj["content"] = signed_data

    der_bytes = asn1obj.dump()
    pem_bytes = pem.armor("CMS", der_bytes)

    return pem_bytes
