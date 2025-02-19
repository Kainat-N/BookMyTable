from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from .models import Payment, PaymentByCard, PaymentByWallet, Card
from reservation.models import Reservation
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from .models import Users

# im using a standard cost for all reservations rn 
STANDARD_RESERVATION_COST = 5  

def send_notification_email(user, subject, message):
    send_mail(
        subject,
        message,
        'bookmytable9@gmail.com', 
        [user.email],
        fail_silently=False,
    )


# View to display payment options (Card or Wallet)
@login_required
def payment_page(request, R_ID, T_ID, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)

    reservation_cost = STANDARD_RESERVATION_COST

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")
        if payment_method == "card":
            return redirect('payment_by_card', R_ID=R_ID, T_ID=T_ID, reservation_id=reservation.id)
        elif payment_method == "wallet":
            return redirect("payment_by_wallet", R_ID=R_ID, T_ID=T_ID, reservation_id=reservation.id)

    # Pass the reservation cost and other details to the template
    return render(
        request,
        "payment/payment_page.html",
        {"reservation": reservation, "reservation_cost": reservation_cost}
    )


# View to process payment via card
@login_required
def payment_by_card(request, R_ID, T_ID, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)

    if reservation.customer != request.user:
        return HttpResponse("You are not authorized to make payment for this reservation.")

    reservation_cost = STANDARD_RESERVATION_COST

    # Fetches user’s saved cards
    user_cards = Card.objects.filter(customer=request.user)

    if request.method == "POST":
        card_option = request.POST.get("card_option")

        if card_option == "existing_card":
            card_id = request.POST.get("card_id")
            card = get_object_or_404(Card, id=card_id, customer=request.user)
            amount = reservation_cost

            payment = PaymentByCard.objects.create(
                amount=amount,
                reservation=reservation,
                saved_card=card,
                status="Completed"
            )
            payment.confirm_payment()
            return redirect("payment_success", R_ID=R_ID, T_ID=T_ID, reservation_id=reservation.id)

        elif card_option == "new_card":
            card_number = request.POST.get("new_card_number")
            expiry_date = request.POST.get("new_card_expiry")
            cardholder_name = request.POST.get("new_card_holder")

            if not all([card_number, expiry_date, cardholder_name]):
                return HttpResponse("All fields are required for adding a new card.")

            # Saving new card 
            new_card = Card.objects.create(
                customer=request.user,
                card_number=card_number,
                expiry_date=expiry_date,
                cardholder_name=cardholder_name
            )

            amount = reservation_cost
            payment = PaymentByCard.objects.create(
                amount=amount,
                reservation=reservation,
                card_number=card_number,
                expiry_date=expiry_date,
                cardholder_name=cardholder_name,
                status="Completed"
            )
            payment.confirm_payment()
            return redirect("payment_success", R_ID=R_ID, T_ID=T_ID, reservation_id=reservation.id)

 
    return render(request, "payment/payment_by_card.html", {
        "reservation": reservation,
        "reservation_cost": reservation_cost,  
        "user_cards": user_cards,
    })


# View to process payment via wallet
@login_required
def payment_by_wallet(request,  R_ID, T_ID, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    reservation_cost = STANDARD_RESERVATION_COST

    if reservation.customer != request.user:
        return HttpResponse("You are not authorized to make payment for this reservation.")

    if request.method == "POST":
        amount = reservation_cost

        if request.user.deduct_from_wallet(amount):
            payment = PaymentByWallet.objects.create(
                amount=amount,
                reservation=reservation,
                status="Completed"
            )
            payment.confirm_payment()
            return redirect("payment_success", R_ID=R_ID, T_ID=T_ID, reservation_id=reservation.id)
        else:
            return HttpResponse("Insufficient funds in your wallet.")

    return render(request, "payment/payment_by_wallet.html", {"reservation": reservation})


# View for payment success
@login_required
def payment_success(request, R_ID, T_ID, reservation_id):
   
    reservation = get_object_or_404(Reservation, id=reservation_id)
    payment = get_object_or_404(Payment, reservation=reservation)

    # Updating the table's is_reserved field to True when payment is successful
    table = reservation.table
    table.is_reserved = True
    table.save()  

    # Updating the reservation's status to "Confirmed"
    reservation.reservation_status = "Confirmed"
    reservation.save()  

    # Sending email notification to the customer
    subject = "Reservation Payment Successful"
    message = (
        f"Dear {reservation.customer.username},\n\n"
        f"Your payment for the reservation at {reservation.restaurant.R_Name} has been successfully processed.\n"
        f"Reservation Details:\n"
        f"Table: {reservation.table.T_ID}\n"
        f"Starting Time: {reservation.starting_time}\n"
        f"Ending Time: {reservation.ending_time}\n\n"
        "Thank you for choosing our service! if you donot come to eat we will eat you"
    )
    send_notification_email(reservation.customer, subject, message)

    return render(request, "payment/payment_success.html", {
        "payment": payment,
        "reservation_id": reservation_id,
        "R_ID": R_ID,
        "T_ID": T_ID
    })
