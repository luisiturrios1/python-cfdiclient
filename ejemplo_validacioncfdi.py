# -*- coding: utf-8 -*-
from cfdiclient import Validacion

validacion = Validacion()
rfc_emisor = 'XAXX010101000'
rfc_receptor = 'XAXX010101000'
total = '1000.41'
uuid = '0XXX0X00-000-0XX0-XX0X-000X0X0XXX00'

estado = validacion.obtener_estado(rfc_emisor, rfc_receptor, total, uuid)

print(estado)
