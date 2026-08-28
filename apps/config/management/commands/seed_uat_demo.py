from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.company.models import Company, CompanyGroup


class Command(BaseCommand):
    help = (
        "Populate a UAT environment with demonstration groups, companies, users, "
        "documents, Peppol/OTA states, notifications, configurations and logs."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete existing application data before loading the demonstration dataset.",
        )

    def handle(self, *args, **options):
        has_business_data = Company.objects.exists() or CompanyGroup.objects.exists()
        if has_business_data and not options["reset"]:
            raise CommandError(
                "Business data already exists. Nothing was changed. Run with --reset only when "
                "you intentionally want to replace this environment with the UAT demo dataset."
            )
        call_command("seed_demo")
        self.stdout.write(self.style.SUCCESS(
            "UAT demonstration data is ready. Login: salim.h@intel-sol.om / Demo@1234 "
            "or superadmin@faturathi.netbue.om / Demo@1234"
        ))
