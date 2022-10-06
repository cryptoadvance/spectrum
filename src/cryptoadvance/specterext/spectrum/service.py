import logging

from cryptoadvance.specter.services.service import Service, devstatus_alpha, devstatus_prod, devstatus_beta
# A SpecterError can be raised and will be shown to the user as a red banner
from cryptoadvance.specter.specter_error import SpecterError
from flask import current_app as app
from flask_apscheduler import APScheduler
from cryptoadvance.spectrum.server import init_app

logger = logging.getLogger(__name__)

class SpectrumService(Service):
    id = "spectrum"
    name = "Spectrum Service"
    icon = "spectrum/img/ghost.png"
    logo = "spectrum/img/logo.jpeg"
    desc = "Where a spectrum grows bigger."
    has_blueprint = True
    blueprint_modules = { 
        "default":  "cryptoadvance.specterext.spectrum.server_endpoints.ui"
    }
    devstatus = devstatus_alpha
    isolated_client = False

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 2

    def callback_after_serverpy_init_app(self, scheduler: APScheduler):
        def every5seconds(hello, world="world"):
            with scheduler.app.app_context():
                print(f"Called {hello} {world} every5seconds")
        # Here you can schedule regular jobs. triggers can be one of "interval", "date" or "cron"
        # Examples:
        # interval: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/interval.html
        # scheduler.add_job("every5seconds4", every5seconds, trigger='interval', seconds=5, args=["hello"])
        
        # Date: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/date.html
        # scheduler.add_job("MyId", my_job, trigger='date', run_date=date(2009, 11, 6), args=['text'])
        
        # cron: https://apscheduler.readthedocs.io/en/3.x/modules/triggers/cron.html
        # sched.add_job("anotherID", job_function, trigger='cron', day_of_week='mon-fri', hour=5, minute=30, end_date='2014-05-30')
        
        # Maybe you should store the scheduler for later use:
        self.scheduler = scheduler
        init_app(app, standalone=False)

    def initial_node_contribution(self):
        pass
