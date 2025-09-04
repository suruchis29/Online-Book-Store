# app/views.py

import pandas as pd 
import json
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from cart.cart import Cart
from .models import Order, Product, Quote, Profile
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User 
from django.contrib import messages
from .forms import SignUpForm, UpdateUserForm, ChangePasswordForm, UserInfoForm
from store.recommend_main import recommend, df
import random
from django.db.models import Q 
from django.http import JsonResponse
from store.topsellingproducts import update_top_selling_products
from django.core.mail import send_mail
from django.conf import settings

def update_prices_view(request):
    updated_products = update_top_selling_products()
    formatted_increased_products = [
        {"id": product['id'], "name": product['name'], "new_price": product['new_price']}
        for product in updated_products['increased_products']
    ]
    formatted_decreased_products = [
        {"id": product['id'], "name": product['name'], "new_price": product['new_price']}
        for product in updated_products['decreased_products']
    ]
    return JsonResponse({
        "message": "Prices updated successfully!",
        "increased_products": formatted_increased_products,
        "decreased_products": formatted_decreased_products
    })

def search(request):
    if request.method == "POST":
        searched = request.POST['searched']
        searched = Product.objects.filter(Q(name__icontains=searched) | Q(description__icontains=searched) | Q(author__icontains=searched))
        if not searched:
            messages.success(request, "That Product Does Not Exist...Please try Again.")
            return render(request, "search.html", {})
        else:
            return render(request, "search.html", {'searched':searched})
    else:
        return render(request, "search.html", {})

def home(request):
    products = Product.objects.all().order_by('-created_at')
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    sale_items = Product.objects.filter(is_sale=True).order_by('-created_at')[:1]
    return render(request, 'home.html',{'products':products,'sale_items':sale_items,'random_quotes':random_quotes})

def about(request):
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    return render(request, 'about.html',{'random_quotes':random_quotes})

def login_user(request):
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            # --- Start of 2FA Logic ---
            if not user.email:
                messages.warning(request, "Your account does not have an email address for 2FA. Please contact support.")
                return render(request, 'login.html', {'random_quotes': random_quotes})

            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['user_id'] = user.id
            
            subject = 'Your Login Verification Code'
            message = f'Hi {user.first_name or user.username},\n\nYour one-time verification code is: {otp}\n\nThis code is valid for a single use.'
            recipient_list = [user.email]
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
            
            messages.success(request, "A verification code has been sent to your email. Please check your inbox.")
            return redirect('verify_otp')
            # --- End of 2FA Logic ---
        else:
            messages.warning(request, "Invalid login details")
            return render(request, 'login.html', {'random_quotes': random_quotes})
    else:
        return render(request, 'login.html', {'random_quotes': random_quotes})

def verify_otp(request):
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    
    if 'user_id' not in request.session:
        messages.warning(request, "Please log in to receive a verification code.")
        return redirect('login')
        
    if request.method == 'POST':
        user_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')
        user_id = request.session.get('user_id')
        
        if user_otp and session_otp and user_id:
            if user_otp == session_otp:
                user = User.objects.get(id=user_id)
                login(request, user)
                
                del request.session['otp']
                del request.session['user_id']
                
                current_user = Profile.objects.get(user__id=user.id)
                saved_cart = current_user.old_cart
                if saved_cart:
                    converted_cart = json.loads(saved_cart)
                    cart = Cart(request)
                    for key, value in converted_cart.items():
                        cart.db_add(product=key, quantity=value)

                messages.success(request, "Login successful, welcome to Book Town")
                return redirect('home')
            else:
                messages.error(request, "Invalid verification code. Please try again.")
                return render(request, 'verify_otp.html', {'random_quotes': random_quotes})
        else:
            messages.error(request, "Session expired or invalid request. Please try to log in again.")
            return redirect('login')
    
    return render(request, 'verify_otp.html', {'random_quotes': random_quotes})


@login_required
def add_order(request):
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    current_user = Profile.objects.get(user__id=request.user.id)
    
    saved_cart = current_user.old_cart
    if saved_cart:
        converted_cart = json.loads(saved_cart)
        cart = Cart(request)
        
        order_details = ""
        total_price = 0
        for key, value in converted_cart.items():
            product_to_add = Product.objects.get(id=int(key))
            product_total_price = product_to_add.price * value
            total_price += product_total_price
            order_details += f"{product_to_add.name} (Quantity: {value}) - Price: NPR {product_total_price}\n"
            
            Order.objects.create(
                product=product_to_add,
                customer=current_user.user,
                quantity=value,
                address=current_user.address,
                phone=current_user.phone,
            )
            
            cart.delete(key)
        
        subject = "Your Order Details"
        message = f"""
        Dear {current_user.user.first_name},

        Your order has been successfully placed. Here are the details:

        {order_details}

        Total Price: NPR {total_price}
        Your order will be shipped to the address:
        {current_user.address}
        

        Thank you for shopping with us!

        ------------------------------------------------------------------------------
        """
        recipient_list = [current_user.user.email]
        
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)

        messages.success(request, "Order created successfully, we will mail you the order details in a while. Thank you for choosing us.")
        
        return render(request, 'cart_summary.html', {'random_quotes': random_quotes})
    else:
        messages.warning(request, "Empty Cart")
        return redirect('home')


def logout_user(request):
    logout(request)
    messages.success(request, ("You have been logged out...Thank you"))
    return redirect('home')

def register_user(request):
    form = SignUpForm()
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()  # Save the user and get the user object
            
            # --- Start of 2FA for Registration ---
            if not user.email:
                # Handle case where user has no email
                user.delete() # Or handle this gracefully
                messages.warning(request, "Your account does not have an email address for 2FA. Registration failed.")
                return redirect('register')

            otp = str(random.randint(100000, 999999))
            request.session['otp'] = otp
            request.session['user_id'] = user.id
            
            subject = 'Welcome to Book Town - Verify Your Email'
            message = f'Hi {user.first_name or user.username},\n\nThank you for registering! Your one-time verification code is: {otp}\n\nThis code is valid for a single use.'
            recipient_list = [user.email]
            
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipient_list)
            
            messages.success(request, "Registration successful! A verification code has been sent to your email to complete the process.")
            return redirect('verify_otp')
            # --- End of 2FA for Registration ---
        else:
            for error in list(form.errors.values()):
                messages.error(request, error)
            return redirect('register')
    else:
        quotes = Quote.objects.all()
        random_quotes = random.choice(quotes) if quotes.exists() else None
        return render(request, 'register.html',{'random_quotes':random_quotes,'form':form})
   
def product(request, pk):
    product = get_object_or_404(Product, id=pk)
    
    df_query = Product.objects.all().values('name', 'author', 'publication', 'price', 'description')
    df = pd.DataFrame(list(df_query))
    
    print("DataFrame columns:", df.columns)
    recommended_books = recommend(df, product.name)

    recommended_products = Product.objects.filter(name__in=recommended_books)
    print(recommended_books)
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None

    return render(request, 'product.html', {
        'product': product,
        'random_quotes': random_quotes,
        'recommended': recommended_products,
    })
   
def product(request, pk):
    product = get_object_or_404(Product, id=pk)
    
    df_query = Product.objects.all().values('name', 'author', 'publication', 'price', 'description')
    df = pd.DataFrame(list(df_query))
    
    print("DataFrame columns:", df.columns)
    recommended_books = recommend(df, product.name)

    recommended_products = Product.objects.filter(name__in=recommended_books)
    print(recommended_books)
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None

    return render(request, 'product.html', {
        'product': product,
        'random_quotes': random_quotes,
        'recommended': recommended_products,
    })


def recommended(request):
    result = recommend(df,"Harry Potter and the Prisoner of Azkaban Book 3")
    print(result)
    results = []
    for i, items in enumerate(result):
        item = Product.objects.filter(name__istartswith=items)
        if item:
            results.append(item)
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    return render(request, 'recommend.html',{'random_quotes':random_quotes, 'recommended':results})  


def update_user(request):
    if request.user.is_authenticated:
        current_user = User.objects.get(id=request.user.id)
        user_form = UpdateUserForm(request.POST or None, instance=current_user)

        if user_form.is_valid():
            user_form.save()

            login(request, current_user)
            messages.success(request, "User Has Been Updated!!")
            return redirect('home')
        return render(request, "update_user.html", {'user_form':user_form})
    else:
        messages.success(request, "You Must Be Logged In To Access That Page!!")
        return redirect('home')


def update_password(request):
    if request.user.is_authenticated:
        current_user = request.user
        if request.method  == 'POST':
            form = ChangePasswordForm(current_user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Your Password Has Been Updated...")
                login(request, current_user)
                return redirect('update_user')
            else:
                for error in list(form.errors.values()):
                    messages.error(request, error)
                    return redirect('update_password')
        else:
            form = ChangePasswordForm(current_user)
            return render(request, "update_password.html", {'form':form})
    else:
        messages.success(request, "You Must Be Logged In To View That Page...")
        return redirect('home')

def update_info(request):
    if request.user.is_authenticated:
        current_user = Profile.objects.get(user__id=request.user.id)
        form = UserInfoForm(request.POST or None, instance=current_user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your Info Has Been Updated!!")
            return redirect('home')
        return render(request, "update_info.html", {'form':form})
    else:
        messages.success(request, "You Must Be Logged In To Access That Page!!")
        return redirect('home')

def order_details(request):
    quotes = Quote.objects.all()
    random_quotes = random.choice(quotes) if quotes.exists() else None
    if request.user.is_authenticated:
        current_order = Order.objects.filter(customer=request.user)
        return render(request, 'order_details.html',{'random_quotes':random_quotes,'orders':current_order, 'username':request.user.first_name})
    
