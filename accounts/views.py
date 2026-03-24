from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required




def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('role_based_redirect')  # or your redirect view
        else:
            return render(request, 'auth/login.html', {
                'error': 'Invalid username or password'
            })

    # ✅ IMPORTANT — always return for GET
    return render(request, 'auth/login.html')





@login_required
def role_based_redirect(request):
    user = request.user

    role = (user.role or "").upper()

    if role == 'FARM':
        return redirect('bottles:farm_entry')

    elif role in ['WAREHOUSE', 'WAREHOUSE STAFF']:
        return redirect('bottles:warehouse_entry')

    elif role == 'DELIVERY':
        return redirect('bottles:delivery_list')

    elif role == 'DRIVER':
        return redirect('bottles:van_entry')

    elif role == 'SUPERVISOR':
        return redirect('bottles:supervisor_panel')

    elif role == 'ADMIN':
        return redirect('dashboard:home')

    else:
        return redirect('login')  # ✅ FIXED


def logout_view(request):
    logout(request)
    return redirect('login')

