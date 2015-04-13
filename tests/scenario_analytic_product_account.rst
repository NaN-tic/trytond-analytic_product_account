=================================
Analytic Product Account Scenario
=================================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock_reservation Module::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...     ('name', 'in', ['analytic_product_account'])])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='Dunder Mifflin')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol='$', code='USD',
    ...     rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...     mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...     rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> AccountTemplate = Model.get('account.account.template')
    >>> Account = Model.get('account.account')
    >>> account_template, = AccountTemplate.find([('parent', '=', None)])
    >>> create_chart = Wizard('account.create_chart')
    >>> create_chart.execute('account')
    >>> create_chart.form.account_template = account_template
    >>> create_chart.form.company = company
    >>> create_chart.execute('create_account')
    >>> receivable, = Account.find([
    ...         ('kind', '=', 'receivable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> payable, = Account.find([
    ...         ('kind', '=', 'payable'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> revenue, = Account.find([
    ...         ('kind', '=', 'revenue'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> expense, = Account.find([
    ...         ('kind', '=', 'expense'),
    ...         ('company', '=', company.id),
    ...         ])
    >>> create_chart.form.account_receivable = receivable
    >>> create_chart.form.account_payable = payable
    >>> create_chart.execute('create_properties')

Create fiscal year::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> fiscalyear = FiscalYear(name='%s' % today.year)
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_sequence = Sequence(name='%s' % today.year,
    ...     code='account.move', company=company)
    >>> post_move_sequence.save()
    >>> fiscalyear.post_move_sequence = post_move_sequence
    >>> fiscalyear.save()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)
    >>> period = fiscalyear.periods[0]


Create analytic accounts::

    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> root = AnalyticAccount(type='root', name='Root')
    >>> root.save()
    >>> analytic_account = AnalyticAccount(root=root, parent=root,
    ...     name='Analytic')
    >>> analytic_account.save()

Create parent product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> AnalyticSelection = Model.get('analytic_account.account.selection')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Parent'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> analytic_selection = AnalyticSelection()
    >>> analytic_selection.accounts.append(analytic_account)
    >>> analytic_selection.save()
    >>> template.analytic_accounts = analytic_selection
    >>> template.save()
    >>> product.template = template
    >>> product.kit = True
    >>> product.save()

Create component A (service) and component B (good)::

    >>> component_a = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Component A'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> component_a.template = template
    >>> component_a.save()

    >>> component_b = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Component B'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> component_b.template = template
    >>> component_b.save()

Make a kit from parent product and check that analytic accounts are created::

    >>> len(analytic_account.childs)
    0
    >>> kit_line = product.kit_lines.new()
    >>> kit_line.product = component_a
    >>> kit_line.quantity = 1
    >>> kit_line = product.kit_lines.new()
    >>> kit_line.product = component_b
    >>> kit_line.quantity = 2
    >>> product.save()
    >>> analytic_account.reload()
    >>> account_a, account_b = analytic_account.childs
    >>> account_a.name
    u'Component A'
    >>> account_b.name
    u'Component B'

If we delete some component analytic account is also deleted::

    >>> _, to_remove = product.kit_lines
    >>> product.kit_lines.remove(to_remove)
    >>> product.save()
    >>> analytic_account.reload()
    >>> account_a, = analytic_account.childs
    >>> account_a.name
    u'Component A'

Components can't be deleted if exists entries on their analytic accounts::

    >>> Party = Model.get('party.party')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(42)
    >>> analytic_line = line.analytic_lines.new()
    >>> analytic_line.journal = journal_revenue
    >>> analytic_line.name = 'Analytic Line'
    >>> analytic_line.credit = line.credit
    >>> analytic_line.account = account_a
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = customer
    >>> move.click('post')
    >>> account_a.reload()
    >>> account_a.credit
    Decimal('42.00')
    >>> to_remove, = product.kit_lines
    >>> product.kit_lines.remove(to_remove)
    >>> product.save()
    Traceback (most recent call last):
        ...
    UserError: ('UserError', (u'You cannot delete component "Component A" because it has associated costs.', ''))

