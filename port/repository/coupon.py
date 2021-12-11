import glob
import os
from xml.dom import minidom

from domain.domains import Coupon, CouponProduct
from port.repository import config


def _parse_aditional_info(aditional_info):
    tokens = aditional_info.split(';')
    info = {}
    field_ctrl = 0
    for token in tokens:
        if field_ctrl == 5:
            break

        elif field_ctrl == 1:
            info['customer_name'] = token.strip(' ')
            field_ctrl += 1

        elif field_ctrl == 2:
            docs = token.split(' ')
            info['customer_document'] = docs[1]
            info['customer_id'] = docs[3]
            field_ctrl += 1

        elif field_ctrl == 3:
            extras = token.split(' ')
            info['plate'] = extras[2]
            field_ctrl += 1
            if len(info['plate']) <= 3 and len(extras) > 3:
                info['plate'] += extras[3]

        elif field_ctrl == 4:
            extras = token.split(' ')
            info['vehicle'] = extras[4]
            field_ctrl += 1

        if token.startswith('FATURA'):
            field_ctrl = 1

    return info


def _get_coupon_status(xml_file):
    status = "NORMAL"
    events_xml = xml_file.replace("-nfe.xml", "-NFeDFe.xml")
    if os.path.isfile(events_xml):
        with open(events_xml) as f:
            if 'Cancelamento de NF-e homologado' in f.read():
                status = "CANCELADO"
    return status


def _get_coupons_of_xml_files():
    xmls_dir = config.get_config('XMLS_DIR')

    for xml_file in glob.iglob(f'{xmls_dir}{os.path.sep}**{os.path.sep}*-nfe.xml', recursive=True):
        root = minidom.parse(xml_file)

        aditional_info = (root.getElementsByTagName('infCpl')[0].firstChild.data or '').upper()

        raw_date = root.getElementsByTagName('dhEmi')[0].firstChild.data.split('T')[0]
        date = "/".join(raw_date.split('-')[::-1])

        info = _parse_aditional_info(aditional_info)
        status = _get_coupon_status(xml_file)

        coupon = Coupon(
            id=root.getElementsByTagName('nNF')[0].firstChild.data,
            aditional_info=aditional_info.upper(),
            date=date,
            status=status,
            **info
        )

        for xml_item in root.getElementsByTagName('prod'):
            product = CouponProduct(
                name=xml_item.getElementsByTagName('xProd')[0].firstChild.data,
                quantity=float(xml_item.getElementsByTagName('qCom')[0].firstChild.data),
                unit_price=float(xml_item.getElementsByTagName('vUnCom')[0].firstChild.data),
                total=float(xml_item.getElementsByTagName('vProd')[0].firstChild.data)
            )
            coupon.products.append(product)

        yield coupon


def find_coupons_greater_than(coupon_number, status='NORMAL'):
    for coupon in _get_coupons_of_xml_files():
        if int(coupon.id) > int(coupon_number) and status == coupon.status:
            yield coupon
