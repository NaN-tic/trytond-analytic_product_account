from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta

__all__ = ['Account', 'ProductKitLine', 'Template', 'Product']


class Account:
    __name__ = 'analytic_account.account'

    kit_line = fields.Many2One('product.kit.line', 'Kit Line')
    parent_kit_line = fields.Many2One('product.product', 'Parent Kit Line')


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
        res = []
        template = self.parent.template
        if not template.parent_analytic_account:
            return res
        parents = [template.parent_analytic_account]
        if template.create_analytic_by_reference:
            if not self.parent.parent_analytic_accounts:
                parent = self.get_analytic_account(
                    template.parent_analytic_account,
                    name=self.parent.template.name)
                parent.kit_line = None
                parent.parent_kit_line = self.parent
                parent.save()
            parents = self.parent.parent_analytic_accounts
        return [self.get_analytic_account(p) for p in parents]

    def get_analytic_account(self, parent, name=None):
        pool = Pool()
        AnalyticAccount = pool.get('analytic_account.account')
        account = AnalyticAccount()
        if name is None:
            account.name = self.product.template.name
        else:
            account.name = name
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


class Template:
    __name__ = 'product.template'

    parent_analytic_account = fields.Many2One('analytic_account.account',
        'Parent Analytic Account')
    create_analytic_by_reference = fields.Boolean(
        'Create Analytic By Reference', help=('If marked an analytic account'
            ' will be created for the parent product of the kit'))

    @staticmethod
    def default_create_analytic_by_reference():
        return True

    @classmethod
    def __setup__(cls):
        super(Template, cls).__setup__()
        if 'parent_analytic_account' not in cls.analytic_accounts.depends:
            states = cls.analytic_accounts.states
            readonly = states.get('readonly', False)
            cls.analytic_accounts.states.update({
                    'readonly': (Bool(readonly) |
                        ~Bool(Eval('parent_analytic_account'))),
                    })
            cls.analytic_accounts.depends.append('parent_analytic_account')


class Product:
    __name__ = 'product.product'

    parent_analytic_accounts = fields.One2Many('analytic_account.account',
        'parent_kit_line', 'Analytic Accounts')
    analytic_configured = fields.Function(fields.Boolean(
            'Analytic Configured'),
        'on_change_with_analytic_configured')

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        if (hasattr(cls, 'kit_lines') and
                'analytic_configured' not in cls.kit_lines.depends):
            states = cls.kit_lines.states
            invisible = states.get('invisible')
            cls.kit_lines.states.update({
                    'invisible': invisible | ~Eval('analytic_configured'),
                    })
            cls.kit_lines.depends.append('analytic_configured')

    def on_change_with_analytic_configured(self, name=None):
        if self.template and self.template.parent_analytic_account:
            return True
        return False
