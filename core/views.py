from django.shortcuts import render

def landing_page(request):
    """Página de bienvenida del sistema SABIX"""
    return render(request, 'landing.html')