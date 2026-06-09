# TNNR Shop Bot 🚘💀

A Telegram bot for managing an underground CPM2 (Car Parking Multiplayer 2) account shop with automated order processing, payment handling, and admin management.

## Features

- 🛒 **Product Shop**: Regular & VIP accounts, Coinfarm system, Email/Password changer
- 🚘 **TNNR Garage**: Premium car inventory management
- 💳 **Multiple Payments**: Telegram Stars, PayPal, PayMaya
- 📦 **Auto Delivery**: Instant account distribution via Telegram Stars
- 📊 **Order Tracking**: Full order history and status management
- ⭐ **Customer Reviews**: Product rating and feedback system
- 👥 **Admin Dashboard**: Inventory management and order verification

## Deployment on Railway

### Prerequisites
- Railway account (https://railway.app)
- GitHub repository
- Telegram Bot Token (from @BotFather)

### Environment Variables

Set these variables in Railway:

```
API_TOKEN=your_telegram_bot_token_here
```

### Deployment Steps

1. **Connect GitHub Repository**
   - Go to Railway.app and create new project
   - Connect your GitHub account
   - Select the TnnrShopBot repository

2. **Add Environment Variables**
   - In Railway project settings, add `API_TOKEN`
   - Use your Telegram bot token from @BotFather

3. **Configure Build Settings**
   - Python version: 3.9+
   - Railway will auto-detect from `requirements.txt`

4. **Deploy**
   - Push changes to main branch
   - Railway will automatically build and deploy
   - Monitor logs in Railway dashboard

### Project Structure

```
TnnrShopBot/
├── testbot (3).py          # Main bot application
├── requirements.txt        # Python dependencies
├── Procfile               # Process configuration
├── .gitignore            # Git ignore rules
├── README.md             # This file
└── tnnr_shop.db          # SQLite database (auto-created)
```

## Database

The bot automatically creates and manages `tnnr_shop.db` with these tables:
- `users` - User registration and purchase history
- `regular_inventory` - Regular account stock
- `vip_inventory` - VIP account stock
- `garage_cars` - TNNR Garage vehicle inventory
- `orders` - Order tracking and status
- `reviews` - Customer reviews and ratings
- `stock_metadata` - Restock timestamps

## Configuration

Edit these values in `testbot (3).py`:

```python
API_TOKEN = 'your_token_here'
OWNER_ID = 6531314640
EXTRA_ADMIN = 8650959684
ADMINS = [OWNER_ID, EXTRA_ADMIN]

STARS_CHANNEL_ID = -1003846885691
LOGS_GROUP_ID = -1003957577057
GARAGE_LOGS_GROUP_ID = -1003957577057

PAYPAL_EMAIL_1 = "email1@gmail.com"
PAYPAL_EMAIL_2 = "email2@gmail.com"

PAYMAYA_NAME = "NAME HERE"
PAYMAYA_NUM = "09281630511"
```

## Admin Commands

- `/restock_regular [qty]` - Add regular accounts to inventory
- `/restock_vip [qty]` - Add VIP accounts to inventory
- `/addcar` - Add new car to TNNR Garage

## User Commands

- `/start` - Start the bot and show main menu
- 🛒 SHOP - Browse products
- 📦 MY ORDERS - Check order status
- 🛍 PREVIEWS - View customer reviews
- 📤 SEND PREVIEWS - Submit product review
- 📜 MY PURCHASE HISTORY - View completed orders

## Payment Flow

1. **Telegram Stars** → Instant automatic delivery
2. **PayPal** → Manual admin verification
3. **PayMaya** → Manual admin verification (Philippines only)

## Admin Order Verification

Admins receive order notifications in the logs group with:
- ✅ CONFIRM ORDER button - Auto-delivers accounts/cars
- ❌ DECLINE ORDER button - Marks order as declined

## Support

For issues or questions:
- Contact: @JustTnnr or @Maarkryan
- Check logs in Railway dashboard
- Review database with SQLite client

---

**Status**: 💯 TRUSTED
**Deployment**: Railway (Automated)
**Language**: Python 3.9+
