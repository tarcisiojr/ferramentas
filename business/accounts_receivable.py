from datetime import datetime, timedelta

from domain.domains import Coupon
from port.repository import accounts_receivable, config
from port.repository.accounts_receivable import create_account_receivable_for_customer, \
    save_account_receivable, exists_account_receivable_for
from port.repository.coupon import find_coupons_from, get_scan_start_date, commit_processed_date, is_already_readed, \
    mark_as_readed


def _add_account_receivable_by_coupon(coupon: Coupon):
    if not exists_account_receivable_for(coupon):
        save_account_receivable(coupon)

        # Commit
        config.write_config('LAST_COUPON', coupon.id)
        print(f'=> cupom {coupon.id} commited!')


def _format_date(date) -> str:
    return date.strftime('%Y%m')


def _to_datetime(str_date: str):
    return datetime.strptime(f'{str_date}15', '%Y%m%d')


def _get_limit_date():
    now = datetime.now()
    return datetime.strptime(now.strftime('%Y%m') + '15', '%Y%m%d')


def _next_month(date):
    new_date = date + timedelta(days=30)
    return datetime(new_date.year, new_date.month, 15)


def sync_acount_receivables():
    date = _to_datetime(get_scan_start_date())
    date_limit = _get_limit_date()

    print('--- iniciando sincronização ---')
    while date <= date_limit:
        str_date = _format_date(date)
        print(f'=> buscandos cupons de {str_date}')
        for coupon in find_coupons_from(str_date):
            if coupon.is_in_cash() or not coupon.is_customer_identified() or is_already_readed(coupon):
                continue

            if not accounts_receivable.exists_account(coupon.customer_id):
                print(f'=> criando conta a receber: {coupon.customer_id} - {coupon.customer_name}')
                create_account_receivable_for_customer(coupon.customer_id, coupon.customer_name)

            print(f'=> adicionando cupom no contas a receber: {coupon.customer_id} - {coupon.customer_name}')
            _add_account_receivable_by_coupon(coupon)
            mark_as_readed(coupon)

        commit_processed_date(_format_date(date))
        date = _next_month(date)

    print('--- fim processamento ---')
