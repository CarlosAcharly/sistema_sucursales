from django.core.management.base import BaseCommand
from django.utils import timezone
from earnings.views import generate_daily_summary

class Command(BaseCommand):
    help = 'Genera resúmenes diarios de ganancias'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, help='Fecha específica (YYYY-MM-DD)')

    def handle(self, *args, **options):
        if options['date']:
            from datetime import datetime
            date = datetime.strptime(options['date'], '%Y-%m-%d').date()
        else:
            date = None
        
        generate_daily_summary(date)
        self.stdout.write(self.style.SUCCESS('Resúmenes generados exitosamente'))