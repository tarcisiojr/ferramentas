import argparse
import dataclasses
import glob
import os
from dataclasses import dataclass
from xml.dom import minidom


@dataclass
class CupomFiscal:
    nome_cliente: str = ''
    documento: str = ''
    nro_cupom: str = ''
    cod_cliente: str = ''
    produto: str = ''
    quantidade: str = '1'
    valor_unitario: str = ''
    valor: str = ''
    veiculo: str = ''
    placa: str = ''
    data: str = ''


def _get_dados_info_adicional(info_adicional):
    tokens = info_adicional.split(';')
    cupom = CupomFiscal()
    campos = 0
    for token in tokens:
        if campos == 5:
            break

        elif campos == 1:
            cupom.nome_cliente = token.strip(' ')
            campos += 1

        elif campos == 2:
            docs = token.split(' ')
            cupom.documento = docs[1]
            cupom.cod_cliente = docs[3]
            campos += 1

        elif campos == 3:
            extras = token.split(' ')
            cupom.placa = extras[2]
            campos += 1
            if len(cupom.placa) <= 3 and len(extras) > 3:
                cupom.placa += extras[3]

        elif campos == 4:
            extras = token.split(' ')
            cupom.veiculo = extras[4]
            campos += 1

        if token.startswith('Fatura'):
            campos = 1
    return cupom


def _escanear_cupons(dir_xml, dir_saida, cli, dt_ini, dt_fim, texto_like):
    total = 0
    total_encontrado = 0
    if not texto_like:
        texto_like = ''

    with open(f'{dir_saida}{os.path.sep}saida.csv', 'w') as saida:
        saida.write(f'DATA;NRO CUPOM;PRODUTO;QUANTIDADE;VALOR UNITÁRIO;VALOR TOTAL;VEICULO;PLACA;STATUS CUPOM\n')

        for arquivo_xml in glob.iglob(f'{dir_xml}{os.path.sep}**{os.path.sep}*-nfe.xml', recursive=True):
            root = minidom.parse(arquivo_xml)
            nro_cupom = root.getElementsByTagName('nNF')[0].firstChild.data
            info_adicional = root.getElementsByTagName('infCpl')[0].firstChild.data
            data_emissao_original = root.getElementsByTagName('dhEmi')[0].firstChild.data.split('T')[0]
            data_emissao_formatada = "/".join(data_emissao_original.split('-')[::-1])

            cupom = _get_dados_info_adicional(info_adicional)
            cupom.nro_cupom = nro_cupom
            cupom.data = data_emissao_formatada

            status = "NORMAL"
            xml_cancelamento = arquivo_xml.replace("-nfe.xml", "-NFeDFe.xml")
            if os.path.isfile(xml_cancelamento):
                with open(xml_cancelamento) as f:
                    if 'Cancelamento de NF-e homologado' in f.read():
                        status = "CANCELADO"

            for prod in root.getElementsByTagName('prod'):
                cupom_produto = dataclasses.replace(cupom)
                cupom_produto.produto = prod.getElementsByTagName('xProd')[0].firstChild.data
                cupom_produto.valor_unitario = prod.getElementsByTagName('vUnCom')[0].firstChild.data
                cupom_produto.quantidade = prod.getElementsByTagName('qCom')[0].firstChild.data
                cupom_produto.valor = prod.getElementsByTagName('vProd')[0].firstChild.data

                if ((cli is None and info_adicional.find(texto_like) >= 0) or (cupom_produto.cod_cliente == cli)) \
                        and (dt_ini <= data_emissao_original <= dt_fim):
                    total_encontrado += 1

                    linha = f'{cupom_produto.data};{cupom_produto.nro_cupom};{cupom_produto.produto};{cupom_produto.quantidade.replace(".", ",")};{cupom_produto.valor_unitario.replace(".", ",")};{cupom_produto.valor.replace(".", ",")};{cupom_produto.veiculo.upper()};{cupom_produto.placa.upper()};{status}'
                    saida.write(f'{linha}\n')
                    print(linha)
            total += 1

    print('----------- Resumo -----------')
    print(f'Total XMLs encontrados: {total}')
    print(f'Total XMLs verificados: {total_encontrado}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli', required=False, help='Código do cliente')
    parser.add_argument('--termo', required=False, help='Busca por texto')
    parser.add_argument('--dt_ini', required=True, help='Data inicial de busca no formato AAAA-MM-DD')
    parser.add_argument('--dt_fim', required=True, help='Data final de busca no formato AAAA-MM-DD')
    parser.add_argument('--dir_xml', required=True, help='Diretorio onde estao localizados os XMLs de cupom fiscal')
    parser.add_argument('--dir_saida', required=True, help='Diretorio de saida do resultado')
    args = parser.parse_args()

    print('Escanenando cupons...')
    print(f'Cliente: {args.cli}')
    print(f'Periodo: {args.dt_ini} a {args.dt_fim}')
    print(f'Diretorio XMLs: {args.dir_xml}')
    print(f'Diretorio saida: {args.dir_saida}')
    print('')
    print('------ Log de execucao -------')

    _escanear_cupons(
        dir_xml=args.dir_xml,
        dir_saida=args.dir_saida,
        cli=args.cli,
        dt_ini=args.dt_ini,
        dt_fim=args.dt_fim,
        texto_like=args.termo
    )

    print('------ Fim de execucao -------')
