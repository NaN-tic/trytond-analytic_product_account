from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__metaclass__ = PoolMeta

__all__ = ['Account', 'ProductKitLine']


class Account:
    __name__ = 'analytic_account.account'

    kit_line = fields.Many2One('product.kit.line', 'Kit Line')


class ProductKitLine:
    __name__ = 'product.kit.line'

    analytic_accounts = fields.One2Many('analytic_account.account', 'kit_line',
        'Analytic Accounts')

    @classmethod
    def __setup__(cls):
        super(ProductKitLine, cls).__setup__()
        cls._error_messages.update({
            'delete_component_with_cost': ('You cannot delete component "%s" '
                    'because it has associated costs.'),
                })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        product_kit_lines = super(ProductKitLine, cls).create(vlist)
        accounts = []
        for pkl in product_kit_lines:
            accounts += pkl.get_missing_analytic_accounts()
        if accounts:
            AnalyticAccount.create([x._save_values for x in accounts])
        cls.create_works(product_kit_lines)
        return product_kit_lines

    def get_missing_analytic_accounts(self):
        existing = {a.parent for a in self.analytic_accounts}
        accounts = {a for a in self.parent.template.analytic_accounts.accounts}
        return [self.get_analytic_account(p) for p in accounts - existing]

    def get_analytic_account(self, parent):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        account = AnalyticAccount()
        account.name = self.product.template.name
        account.parent = parent
        account.root = parent.root
        account.type = 'normal'
        account.currency = parent.currency
        account.company = parent.company
        account.display_balance = parent.display_balance
        account.kit_line = self
        return account

    @classmethod
    def delete(cls, lines):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        to_delete = []
        for line in lines:
            to_delete += line.analytic_accounts
        cls.check_delete(to_delete)
        AnalyticAccount.delete(to_delete)
        super(ProductKitLine, cls).delete(lines)

    @classmethod
    def check_delete(cls, accounts):
        pool = Pool()
        AnalyticLine = pool.get('analytic_account.line')
        lines = AnalyticLine.search([
                ('account', 'in', [a.id for a in accounts]),
                ], limit=1)
        if lines:
            line, = lines
            cls.raise_user_error('delete_component_with_cost',
                line.account.rec_name)

    @classmethod
    def create_works(cls, lines):
        pool = Pool()
        try:
            Work = pool.get('timesheet.work')
        except KeyError:
            return
        to_create = []
        for line in lines:
            if not hasattr(line.product, 'works'):
                return
            to_create += line.get_work_values()
        return Work.create(to_create)

    def get_work_values(self):
        values = []
        for account in self.analytic_accounts:
            value = {
                'name': account.full_name,
                'timesheet_available': True,
                'company': Transaction().context.get('company'),
                'product': self.product.id,
                'account': account.id,
            }
            values.append(value)
        return values
