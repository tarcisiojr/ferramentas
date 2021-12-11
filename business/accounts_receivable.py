from time import sleep

from domain.domains import Coupon
from port.repository import accounts_receivable, config
from port.repository.accounts_receivable import get_last_readed_coupon_number, create_account_receivable_for_customer, \
    save_account_receivable
from port.repository.coupon import find_coupons_greater_than


def _add_account_receivable_by_coupon(coupon: Coupon):
    save_account_receivable(coupon)

    # Commit
    config.write_config('LAST_COUPON', coupon.id)
    print(f'=> cupom {coupon.id} commited!')


def sync_acount_receivables():
    last_coupon = get_last_readed_coupon_number()
    count = 0

    for coupon in find_coupons_greater_than(last_coupon):
        if coupon.is_in_cash() or not coupon.is_customer_identified():
            continue

        print('=> esperando alguns segundos...')
        sleep(5)

        if not accounts_receivable.exists_account(coupon.customer_id):
            create_account_receivable_for_customer(coupon.customer_id, coupon.customer_name)

        print(f'=> adicionando cupom no contas a receber: {coupon.customer_id} - {coupon.customer_name}')
        _add_account_receivable_by_coupon(coupon)

    print('--- fim processamento ---')
