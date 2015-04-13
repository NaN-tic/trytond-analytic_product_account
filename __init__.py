# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .product import *


def register():
    Pool.register(
        Account,
        ProductKitLine,
        module='analytic_product_account', type_='model')
