# -*- coding: utf-8 -*-
import base64

from Crypto.Hash import SHA
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from OpenSSL import crypto


class Fiel():
    def __init__(self, cer_der, key_der, passphrase):
        self.__importar_cer__(cer_der)
        self.__importar_key__(key_der, passphrase)

    def __importar_cer__(self, cer_der):
        self.cer = crypto.load_certificate(crypto.FILETYPE_ASN1, cer_der)

    def __importar_key__(self, key_der, passphrase):
        # Importar KEY
        self.key = RSA.importKey(key_der, passphrase)
        # Crear objeto para firmar
        self.signer = PKCS1_v1_5.new(self.key)

    def firmar(self, texto):
        # Generar SHA1
        sha1 = SHA.new(texto)
        # Firmar
        firma = self.signer.sign(sha1)
        # Pasar a base64
        b64_firma = base64.b64encode(firma)
        return b64_firma

    def cer_to_base64(self):
        cer = crypto.dump_certificate(crypto.FILETYPE_ASN1, self.cer)
        return base64.b64encode(cer)

    def cer_issuer(self):
        d = self.cer.get_issuer().get_components()
        datos = ''
        for t in d:
            datos += '{}={},'.format(t[0], t[1])
        return datos[:-1].decode('utf8')
    
    def cer_serial_number(self):
        serial = self.cer.get_serial_number()
        return str(serial)
