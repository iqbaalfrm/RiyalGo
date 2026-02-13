import re

f = 'templates/index.html'
with open(f, 'r', encoding='utf-8') as file:
    c = file.read()

# 1. HEADER CLEANUP
# - Remove version from title
c = c.replace('>KODOKRIYAL v2.1.0</span>', '>KODOKRIYAL</span>')

# - Hide Status & Binance on mobile completely
# Current: <div class="flex items-center gap-2 md:gap-4 ... border-l border-white/10 pl-2 md:pl-4 ...">
# New: <div class="hidden md:flex items-center gap-4 text-white/50 border-l border-white/10 pl-4 whitespace-nowrap">
c = c.replace(
    'flex items-center gap-2 md:gap-4 text-white/50 border-l border-white/10 pl-2 md:pl-4 text-[9px] md:text-xs whitespace-nowrap',
    'hidden md:flex items-center gap-4 text-white/50 border-l border-white/10 pl-4 whitespace-nowrap'
)

# - Restore simple status labels (since hidden on mobile, no need for complex span structure)
c = c.replace('<span><span class="hidden sm:inline">STATUS: </span><span id="system-status"', '<span>STATUS: <span id="system-status"')
c = c.replace('<span><span class="hidden sm:inline">BINANCE: </span><span id="binance-status"', '<span>KONEKSI BINANCE: <span id="binance-status"')

# - Clock: Show ONLY time on mobile
# We need JS adjustment for this.
# HTML structure: <span class="block font-mono text-[9px] md:text-sm whitespace-nowrap" id="digital-clock">
# Let's add a specialized structure: 
# <span class="block font-mono text-[9px] md:text-sm whitespace-nowrap">
#   <span id="clock-time">--:--</span> <span class="hidden md:inline" id="clock-date">| --/--/----</span>
# </span>

# Replace the clock span
c = c.replace(
    '<span class="block font-mono text-[9px] md:text-sm whitespace-nowrap" id="digital-clock">--:--:-- WIB | --/--/----</span>',
    '<span class="font-mono text-[10px] md:text-sm text-white/80" id="digital-clock">--:--</span>'
)
# Note: I'll simplify the JS to just output time on mobile or use CSS hiding?
# Easier: Just let JS update 'digital-clock' with time only on mobile?
# No, easier to just update JS to format nicely.
# Let's change the JS to update two spans if possible, or just formatted string.
# Actually, the user wants "jam tanpa tanggal".
# JS defines: `${d.time} WIB | ${d.date}`
# I will change JS to update consistent format or use CSS.

# Let's change the JS update logic in `updateClock` function
# Find: document.getElementById('digital-clock').textContent = ...
# Replace with logic that checks screen width? No, server side rendering / client side JS.
# Better: Update `updateClock` to show only time if window.innerWidth < 768?
# Or just distinct elements.
pass

with open(f, 'w', encoding='utf-8') as file:
    file.write(c)

print("HTML structure updated.")
