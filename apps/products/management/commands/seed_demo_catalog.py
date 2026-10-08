from django.core.management.base import BaseCommand

from apps.products.models import Product


DEMO_PRODUCTS = (
    ('Astra 14 Pro Laptop', 'laptops', 48900000, '14-inch laptop with 16 GB memory, fast solid-state storage, vivid display, and lightweight aluminum chassis for study and work.'),
    ('Forge 15 Gaming Laptop', 'laptops', 79900000, 'Gaming notebook with high-refresh display, discrete graphics, dual-fan cooling, customizable keyboard lighting, and upgradeable memory.'),
    ('Nomad 13 Ultrabook', 'laptops', 52900000, 'Ultraportable 13-inch laptop with bright display, long battery design, Wi-Fi 6, and comfortable backlit keyboard.'),
    ('Pixel 16 OLED Laptop', 'laptops', 92900000, 'OLED laptop with deep contrast, accurate color, modern multi-core performance, and precision touchpad for creative work.'),
    ('Slate 14 Student Laptop', 'laptops', 36900000, 'Everyday laptop with 14-inch display, 512 GB SSD, webcam privacy control, and lightweight design for classes.'),
    ('Vector 17 Gaming Laptop', 'laptops', 115900000, 'Large gaming laptop pairing a 17-inch high-refresh panel with advanced graphics, reinforced hinges, and RGB lighting.'),
    ('Keycraft TKL Mechanical Keyboard', 'keyboards', 8490000, 'Tenkeyless mechanical keyboard with hot-swappable tactile switches, per-key lighting, durable PBT caps, and USB-C.'),
    ('Keycraft 75 Wireless Keyboard', 'keyboards', 11200000, 'Compact 75-percent layout with Bluetooth and 2.4 GHz wireless, multi-device switching, and long battery life.'),
    ('Arc 65 Gaming Keyboard', 'keyboards', 9790000, 'Compact gaming keyboard with hot-swap sockets, responsive switches, and configurable RGB effects.'),
    ('Pulse 27 Gaming Monitor', 'gaming', 31900000, '27-inch QHD gaming monitor with 180 Hz refresh rate, adaptive sync, and height-adjustable stand.'),
    ('Vector Wireless Gaming Mouse', 'gaming', 6490000, 'Lightweight wireless gaming mouse with precise optical sensor, programmable buttons, and onboard profiles.'),
    ('Carbon Pro Gaming Headset', 'gaming', 8790000, 'Closed-back gaming headset with detachable microphone, spatial audio support, and memory foam cushions.'),
    ('AeroStream USB Microphone', 'gaming', 7390000, 'Plug-and-play USB microphone with cardioid pickup, touch mute, gain control, and compact desk stand.'),
    ('Glide XL Desk Mat', 'accessories', 1890000, 'Stitched-edge extended desk mat with smooth tracking surface, grippy base, and room for keyboard and mouse.'),
    ('Dockline USB-C Laptop Dock', 'accessories', 7890000, 'Compact USB-C dock with HDMI, Ethernet, USB-A, card reader, and pass-through power for laptop desks.'),
    ('Volt 100W GaN Charger', 'accessories', 3890000, 'Compact multi-port USB-C charger with up to 100 W output for laptops, tablets, and phones.'),
    ('Cobalt Laptop Sleeve 14', 'accessories', 1790000, 'Padded 14-inch laptop sleeve with water-resistant exterior, soft lining, accessory pocket, and reinforced zipper.'),
    ('Aurum Core i5 14th Gen Processor', 'cpus', 22900000, '14th-generation desktop processor sample listing for gaming and productivity builds. Confirm motherboard socket and BIOS compatibility before purchase.'),
    ('Aurum Core i7 14th Gen Processor', 'cpus', 38900000, 'High-performance 14th-generation desktop processor sample listing for demanding games and creation workloads. Confirm board compatibility before purchase.'),
    ('Aurum Core i9 14th Gen Processor', 'cpus', 58900000, 'Enthusiast 14th-generation desktop processor sample listing for high-end gaming and multithreaded tasks. Pair with suitable cooling and a compatible motherboard.'),
    ('Vortex RTX-Class 16GB Graphics Card', 'gpus', 79900000, 'High-end discrete graphics card sample with 16 GB video-memory class, ray-tracing support, and modern display outputs.'),
    ('Vortex RTX-Class 12GB Graphics Card', 'gpus', 52900000, 'Performance graphics card sample with 12 GB video-memory class for high-refresh 1440p gaming.'),
    ('Pulse Radeon-Class 16GB Graphics Card', 'gpus', 64900000, 'Discrete graphics card sample with 16 GB video-memory class, efficient triple-fan cooling, and modern gaming features.'),
    ('Spectra DDR5 32GB Memory Kit', 'ram', 11900000, 'Matched 2 x 16 GB DDR5 desktop memory sample kit. Confirm supported speed and capacity against the motherboard and CPU.'),
    ('Spectra DDR5 64GB Memory Kit', 'ram', 21900000, 'Matched 2 x 32 GB DDR5 memory sample kit for large projects and gaming workstations. Confirm motherboard capacity and profile support.'),
    ('Neon RGB DDR5 32GB Memory Kit', 'ram', 14900000, 'Illuminated 2 x 16 GB DDR5 memory sample kit with configurable lighting and aluminum heat spreaders.'),
    ('Apex 27 QHD 180Hz Gaming Monitor', 'monitors', 32900000, '27-inch QHD gaming monitor sample with 180 Hz refresh class, adaptive sync, adjustable stand, and low-latency modes.'),
    ('Apex 32 4K Gaming Monitor', 'monitors', 58900000, '32-inch 4K gaming monitor sample with vivid color, adaptive sync, height adjustment, and high-speed inputs.'),
    ('Apex 24 FHD 240Hz Gaming Monitor', 'monitors', 26900000, '24-inch full-HD esports monitor sample with 240 Hz refresh class, fast-response settings, and adjustable stand.'),
    ('Aquarium Gen 14 Gaming PC Build', 'pcs', 189000000, 'Complete aquarium-style panoramic glass gaming PC sample build with 14th-generation processor, discrete graphics, 32 GB DDR5 memory, 2 TB NVMe storage, 360 mm liquid cooling, and 850 W power supply. Exact component brands and final compatibility must be confirmed.'),
    ('Full-Size Aurora Mechanical Gaming Keyboard', 'keyboards', 10400000, 'Full-size mechanical gaming keyboard with numeric keypad, hot-swappable switches, per-key RGB lighting, and USB-C connection.'),
    ('Atlas B760 Wi-Fi DDR5 Motherboard', 'motherboards', 21900000, 'Gaming motherboard sample with DDR5 memory support, integrated Wi-Fi, multiple M.2 slots, and PCIe expansion. Verify exact processor socket and BIOS compatibility.'),
    ('Atlas X670 Wi-Fi AM5 Motherboard', 'motherboards', 34900000, 'AM5 gaming motherboard sample with DDR5 support, Wi-Fi, multiple high-speed M.2 slots, and reinforced graphics slot. Check CPU and case fit before purchase.'),
    ('Swift 1TB PCIe 4.0 NVMe SSD', 'storage', 8900000, '1 TB M.2 NVMe solid-state drive sample for fast game and application loading. Confirm M.2 length and PCIe support.'),
    ('Swift 2TB PCIe 4.0 NVMe SSD', 'storage', 15900000, '2 TB M.2 NVMe solid-state drive sample with high-speed PCIe 4.0 storage for a gaming library and creative projects.'),
    ('Titan 850W 80 Plus Gold Power Supply', 'power', 16900000, '850 W modular 80 Plus Gold PSU sample for performance gaming systems. Check GPU power connectors and total system draw.'),
    ('Titan 1000W ATX 3.0 Power Supply', 'power', 23900000, '1000 W ATX 3.0 modular PSU sample with modern high-power GPU cable support and 80 Plus Gold efficiency class.'),
    ('Boreal 360mm Liquid CPU Cooler', 'cooling', 18900000, '360 mm all-in-one liquid CPU cooler sample with three fans. Confirm radiator clearance, socket support, and case compatibility.'),
    ('Boreal Dual-Tower Air CPU Cooler', 'cooling', 7900000, 'Dual-tower air cooler sample with two quiet fans and broad socket support. Confirm memory and case height clearance.'),
    ('Panorama Mesh ATX Gaming Case', 'cases', 12900000, 'Airflow-focused ATX case sample with mesh front, tempered-glass side panel, and room for long graphics cards. Verify radiator and motherboard fit.'),
    ('Compact Forge Micro-ATX Gaming Case', 'cases', 9900000, 'Compact mesh-front Micro-ATX case sample with tempered glass and flexible fan mounting. Check motherboard and GPU dimensions.'),
)

LEGACY_DEMO_NAMES = ('Meridian Wireless Headphones', 'Quiet Arc ANC Earbuds', 'Deskwave Bluetooth Speaker', 'Studio Monitor Headphones', 'Open Air Clip Headphones', 'Drift Travel Headphones', 'Summit GPS Sports Watch', 'Pulse Everyday Smartwatch', 'Slate Fitness Band', 'Rest Cycle Sleep Tracker', 'Metro Step Watch', 'Halo Portable Table Lamp', 'Ember Sunrise Alarm Lamp', 'Airloom Quiet Desk Fan', 'Calm Mist Aroma Diffuser', 'Cove Bedside Reading Light', 'Nest Room Sensor Hub', 'Focus Wool Desk Mat', 'Orbit USB-C Desk Dock', 'Paperlight E-Reader', 'Lift Aluminum Laptop Stand', 'Beam Monitor Light Bar', 'Typewell Mechanical Keyboard', 'Stoneware Pour-Over Set', 'Steady Gooseneck Kettle', 'Millstone Burr Grinder', 'Daybreak Cold Brew Carafe', 'Blend Go Portable Blender', 'Flow Grip Yoga Mat', 'Trail Resistance Band Kit', 'Stride Speed Jump Rope', 'Core Recovery Roller', 'Tempo Smart Jump Rope', 'Roam Carry-On Backpack', 'Foldaway Packing Organizer Set', 'Northline Wireless Power Bank', 'Everywhere Travel Adapter', 'Cloud Compression Packing Cubes', 'Quiet Night Sleep Mask')


class Command(BaseCommand):
    help = "Create a laptop and gaming-focused sample catalog for storefront and LLM testing."

    def handle(self, *args, **options):
        Product.objects.filter(name__in=LEGACY_DEMO_NAMES).update(is_available=False)
        Product.objects.exclude(category__in=["laptops", "keyboards", "gaming", "accessories", "cpus", "gpus", "ram", "monitors", "pcs", "other", "motherboards", "storage", "power", "cooling", "cases"]).update(is_available=False)
        created = 0
        existing = 0
        for name, category, price, description in DEMO_PRODUCTS:
            product, was_created = Product.objects.get_or_create(
                name=name,
                defaults={
                    "category": category,
                    "price": price,
                    "description": description,
                    "is_available": True,
                    "stock": 12,
                },
            )
            if not was_created and not product.is_available:
                product.is_available = True
                product.save(update_fields=["is_available"])
            if not was_created and (product.category != category or product.price != price or product.description != description):
                product.category = category
                product.price = price
                product.description = description
                product.is_available = True
                product.save(update_fields=["category", "price", "description", "is_available"])
            if not was_created and product.stock is None:
                product.stock = 12
                product.save(update_fields=["stock"])
            created += int(was_created)
            existing += int(not was_created)
        self.stdout.write(
            self.style.SUCCESS(
                f"Catalog ready: {created} products added, {existing} already existed."
            )
        )
