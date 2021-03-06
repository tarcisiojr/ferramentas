from __future__ import print_function

import os.path
from contextvars import ContextVar
from typing import List

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from domain.domains import Coupon
from port.repository import config
from port.repository.util import RatelimitControl

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

_credentials = ContextVar("credentials", default=None)
_cache_summary = ContextVar("cache_summart", default=[])
_cache_summary_header = ContextVar("_cache_summary_header", default={})
_ratelimit_read = RatelimitControl('read', 55)
_ratelimit_write = RatelimitControl('write', 50)
_rows_buffer = ContextVar('rows_buffer', default=[])
_spreadsheet = ContextVar('spreadsheet', default={})


SPREADSHEET_NAME_SUMMARY = "SUMMARY"
SPREADSHEET_NAME_TEMPLATE = "TEMPLATE"
SPREADSHEET_FOLDER = "CUSTOMER_FOLDER"

BUFFER_ROWS_SIZE = 50


def _lock(read_ops=0, write_ops=0):
    _ratelimit_read.lock(read_ops)
    _ratelimit_write.lock(write_ops)


def _create_credentials():
    print('=> autenticando no Google')
    _lock(read_ops=2)
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def _get_credentials():
    if not _credentials.get():
        _credentials.set(_create_credentials())

    return _credentials.get()


def _get_spreadsheet_id(name: str) -> str:
    return config.get_config(name)


def _get_spreadsheet_by_fileid(fileid):
    _lock(read_ops=2)
    gc = gspread.authorize(_get_credentials())
    return gc.open_by_key(fileid)


def _get_spreadsheet(spreadsheet_id):
    return _get_spreadsheet_by_fileid(_get_spreadsheet_id(spreadsheet_id))


def _get_cache_summary() -> List[List[str]]:
    if not _cache_summary.get():
        spreadsheet = _get_spreadsheet(SPREADSHEET_NAME_SUMMARY)
        _cache_summary.set(spreadsheet.get_worksheet(0).get_values())

    return _cache_summary.get()


def _create_customer_ar_from_template(customer_id, customer_name):
    _lock(write_ops=1)
    template_file_id = config.get_config(SPREADSHEET_NAME_TEMPLATE)
    folder_id = config.get_config(SPREADSHEET_FOLDER)
    file_name = f'{customer_id} - {customer_name.upper()}'
    service = build('drive', 'v3', credentials=_create_credentials())
    return service.files().copy(fileId=template_file_id, body={'name': file_name, 'parents': [folder_id]}).execute()


def _get_last_row(sheet, cols_to_sample=1):
    _lock(read_ops=1)
    # looks for empty row based on values appearing in 1st N columns
    cols = sheet.range(1, 1, sheet.row_count, cols_to_sample)
    return max([cell.row for cell in cols if cell.value])


def _create_col_index(worksheet):
    _lock(read_ops=1)
    values = worksheet.row_values(1)
    index = {}
    for i in range(0, len(values)):
        index[values[i]] = i
    return index


def _get_col_index_from_sumary_header(col_name):
    if not _cache_summary_header.get().get(col_name):
        _lock(read_ops=1)
        spreadsheet = _get_spreadsheet(SPREADSHEET_NAME_SUMMARY)
        worksheet = spreadsheet.worksheet('RESUMO')
        index = _create_col_index(worksheet)
        _cache_summary_header.set(index)

    return _cache_summary_header.get().get(col_name)


def _get_fileid_of_customer(customer_id) -> str:
    values = _get_cache_summary()
    for i in range(1, len(values)):
        if values[i][_get_col_index_from_sumary_header('ID CLIENTE')] == customer_id:
            return values[i][_get_col_index_from_sumary_header('ID PLANILHA')]
    return None


def _append_copied_row(spreadsheet, row_from, row_to, total_cols):
    body = {
        "requests": [
            {
                "copyPaste": {
                    "source": {
                        "sheetId": 0,
                        "startRowIndex": row_from,
                        "endRowIndex": row_from + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": total_cols
                    },
                    "destination": {
                        "sheetId": 0,
                        "startRowIndex": row_to,
                        "endRowIndex": row_to + 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": total_cols
                    },
                    "pasteType": "PASTE_NORMAL"
                }
            }
        ]
    }
    _lock(write_ops=1)
    spreadsheet.batch_update(body)


def _copy_formulas(spreadsheet, row_from, row_to, total_rows, col_from, col_to):
    body = {
        "requests": [
            {
                "copyPaste": {
                    "source": {
                        "sheetId": 0,
                        "startRowIndex": row_from,
                        "endRowIndex": row_from + 1,
                        "startColumnIndex": col_from,
                        "endColumnIndex": col_to
                    },
                    "destination": {
                        "sheetId": 0,
                        "startRowIndex": row_to,
                        "endRowIndex": row_to + total_rows,
                        "startColumnIndex": col_from,
                        "endColumnIndex": col_to
                    },
                    "pasteType": "PASTE_NORMAL"
                }
            }
        ]
    }
    spreadsheet.batch_update(body)


def _get_sheet_data_of(coupon: Coupon):
    fileid = _get_fileid_of_customer(coupon.customer_id)
    spreadsheet = _get_spreadsheet_by_fileid(fileid)
    _lock(read_ops=1)
    worksheet = spreadsheet.worksheet('CONTAS-A-PAGAR')
    return spreadsheet, worksheet


def create_account_receivable_for_customer(customer_id: str = '', customer_name: str = ''):
    file = _create_customer_ar_from_template(customer_id, customer_name)

    spreadsheet = _get_spreadsheet(SPREADSHEET_NAME_SUMMARY)
    _lock(read_ops=1)
    worksheet = spreadsheet.worksheet('RESUMO')

    col_index = _create_col_index(worksheet)
    last_row = _get_last_row(worksheet)
    total_cols = len(col_index.keys())

    _append_copied_row(spreadsheet, last_row - 1, last_row, total_cols)

    _lock(write_ops=3)
    worksheet.update_cell(last_row + 1, col_index.get('ID PLANILHA') + 1, file.get('id'))
    worksheet.update_cell(last_row + 1, col_index.get('ID CLIENTE') + 1, customer_id)
    worksheet.update_cell(last_row + 1, col_index.get('CLIENTE') + 1, customer_name)

    _cache_summary.set([])


def exists_account_receivable_for_v1(coupon: Coupon) -> bool:
    _lock(read_ops=2)
    spreadsheet, worksheet = _get_sheet_data_of(coupon)
    return worksheet.find(coupon.id, in_column=2) is not None


def _get_ar_spreadsheet():
    if not _spreadsheet.get().get('spreadsheet'):
        _lock(read_ops=2)
        spreadsheet = _get_spreadsheet_by_fileid(config.get_config('ACCOUNT_RECEIVABLE_SPREADSHEET'))
        worksheet = spreadsheet.worksheet('CONTAS-A-RECEBER')
        _spreadsheet.set({'spreadsheet': spreadsheet, 'worksheet': worksheet})

    return _spreadsheet.get().get('spreadsheet'), _spreadsheet.get().get('worksheet')


def exists_account_receivable_for(coupon: Coupon) -> bool:
    _, worksheet = _get_ar_spreadsheet()
    _lock(read_ops=1)
    return worksheet.find(coupon.id, in_column=2) is not None or [1 for row in _rows_buffer.get() if row[1] == coupon.id]


def save_account_receivable_v1(coupon: Coupon):
    spreadsheet, worksheet = _get_sheet_data_of(coupon)

    col_index = _create_col_index(worksheet)
    last_row = _get_last_row(worksheet)
    total_cols = len(col_index.keys())

    _append_copied_row(spreadsheet, last_row - 1, last_row, total_cols)

    _lock(write_ops=4)
    worksheet.update_cell(last_row+1, col_index.get('DATA')+1, coupon.date)
    worksheet.update_cell(last_row + 1, col_index.get('CUPOM') + 1, coupon.id)
    worksheet.update_cell(last_row + 1, col_index.get('VALOR TOTAL') + 1, coupon.total)
    worksheet.update_cell(last_row + 1, col_index.get('DT PAGTO') + 1, '')
    # worksheet.append_rows()


def exists_account(customer_id):
    values = _get_cache_summary()
    for i in range(1, len(values)):
        if values[i][_get_col_index_from_sumary_header('ID CLIENTE')] == customer_id:
            return True
    return False


def flush_pending_savings():
    if not len(_rows_buffer.get()):
        return []

    spreadsheet, worksheet = _get_ar_spreadsheet()
    last_row = _get_last_row(worksheet)

    _lock(write_ops=2)
    worksheet.append_rows(_rows_buffer.get())
    _copy_formulas(spreadsheet, 1, last_row, len(_rows_buffer.get()), 5, 13)
    _rows_buffer.set([])
    return [row[1] for row in _rows_buffer.get()]


def save_account_receivable(coupon: Coupon):
    if len(_rows_buffer.get()) < BUFFER_ROWS_SIZE:
        _rows_buffer.set(_rows_buffer.get() + [
            [coupon.date, coupon.id, coupon.customer_id, coupon.customer_name, coupon.total]
        ])
        return []

    return flush_pending_savings()

