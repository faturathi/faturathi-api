from django.core.management.base import BaseCommand, CommandError

from apps.company.models import Company
from apps.config.demo_logs import populate_demo_logs


class Command(BaseCommand):
    help = "Populate deterministic user, OTA/AS4, server/API, error and warning logs for demo/UAT."

    def add_arguments(self, parser):
        parser.add_argument("--company", help="Limit logs to one company short code, for example E1.")
        parser.add_argument(
            "--clear-demo", action="store_true",
            help="Delete only rows created by this command before rebuilding them. Real audit logs are preserved.",
        )

    def handle(self, *args, **options):
        companies = Company.objects.filter(is_active=True).order_by("short_code")
        if options.get("company"):
            companies = companies.filter(short_code__iexact=options["company"])
        if not companies.exists():
            raise CommandError("No matching active company exists. Populate companies first with seed_uat_demo.")
        result = populate_demo_logs(companies=companies, clear_demo=options["clear_demo"])
        self.stdout.write(self.style.SUCCESS(
            f"Demo logs ready: {result['total']} rows across {result['companies']} companies "
            f"({result['created']} created, {result['updated']} refreshed)."
        ))
