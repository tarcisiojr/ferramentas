import glob
import json
import os
from contextvars import ContextVar
from xml.dom import minidom

from domain.domains import Coupon, CouponProduct
from port.repository import config

_readed_coupons = ContextVar("readed_coupons", default=[])


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


def _get_coupons_of_xml_files(dir_date):
    xmls_dir = config.get_config('XMLS_DIR')

    for xml_file in glob.iglob(f'{xmls_dir}{os.path.sep}**{os.path.sep}{dir_date}{os.path.sep}*-nfe.xml', recursive=True):
        print(f'=> file {xml_file}')

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


def find_coupons_from(str_date: str, status='NORMAL'):
    for coupon in _get_coupons_of_xml_files(str_date):
        if status == coupon.status:
            yield coupon


def get_scan_start_date():
    return config.get_config('START_SCAN_AT')


def commit_processed_date(str_date):
    config.write_config('START_SCAN_AT', str_date)


def get_readed_coupon_ids():
    if not _readed_coupons.get():
        if os.path.exists('./cupons.json'):
            with open('./cupons.json') as file:
                coupons = json.load(file)
                _readed_coupons.set(coupons or [])
    return _readed_coupons.get()


def mark_as_readed(coupons_ids):
    _readed_coupons.set(get_readed_coupon_ids() + coupons_ids)

    with open('./cupons.json', 'w') as file:
        json.dump(_readed_coupons.get() or [], file)

    print(f'=> marcado {len(coupons_ids)} cupons como lido!')


def is_already_readed(coupon: Coupon) -> bool:
    return coupon.id in get_readed_coupon_ids()

