---
name: Ivorian Merchant Premium
colors:
  surface: '#f9f9fc'
  surface-dim: '#dadadc'
  surface-bright: '#f9f9fc'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f6'
  surface-container: '#eeeef0'
  surface-container-high: '#e8e8ea'
  surface-container-highest: '#e2e2e5'
  on-surface: '#1a1c1e'
  on-surface-variant: '#574235'
  inverse-surface: '#2f3133'
  inverse-on-surface: '#f0f0f3'
  outline: '#8b7263'
  outline-variant: '#dec1af'
  surface-tint: '#954a00'
  primary: '#954a00'
  on-primary: '#ffffff'
  primary-container: '#ff8200'
  on-primary-container: '#5f2c00'
  inverse-primary: '#ffb785'
  secondary: '#006d30'
  on-secondary: '#ffffff'
  secondary-container: '#7efc9a'
  on-secondary-container: '#007434'
  tertiary: '#005db6'
  on-tertiary: '#ffffff'
  tertiary-container: '#6ba5ff'
  on-tertiary-container: '#003a75'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdcc6'
  primary-fixed-dim: '#ffb785'
  on-primary-fixed: '#301400'
  on-primary-fixed-variant: '#723700'
  secondary-fixed: '#7efc9a'
  secondary-fixed-dim: '#60df81'
  on-secondary-fixed: '#00210a'
  on-secondary-fixed-variant: '#005323'
  tertiary-fixed: '#d6e3ff'
  tertiary-fixed-dim: '#a9c7ff'
  on-tertiary-fixed: '#001b3d'
  on-tertiary-fixed-variant: '#00468c'
  background: '#f9f9fc'
  on-background: '#1a1c1e'
  surface-variant: '#e2e2e5'
typography:
  display-lg:
    fontFamily: Public Sans
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Public Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Public Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  title-lg:
    fontFamily: Public Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  body-lg:
    fontFamily: Public Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Public Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-lg:
    fontFamily: Public Sans
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.05em
  label-md:
    fontFamily: Public Sans
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  gutter: 16px
  margin-mobile: 16px
  margin-tablet: 32px
---

## Brand & Style
The brand personality is defined by the concept of "Trusted Vitality." It reflects the rapid economic emergence of Côte d'Ivoire, blending the reliability of a high-end financial institution with the vibrant, entrepreneurial energy of Ivorian commerce. The design system targets merchants ranging from high-end boutiques in Abidjan to high-volume wholesalers, requiring a UI that feels both prestigious and exceptionally functional.

The chosen style is **Corporate / Modern** with **Minimalist** influences. It prioritizes clarity and efficiency, utilizing significant whitespace to reduce cognitive load during fast-paced transactions. The aesthetic is professional and secure, using the national colors to foster an immediate sense of local ownership and patriotic pride without descending into kitsch.

## Colors
The color palette is anchored by the national identity of Côte d'Ivoire. **Primary Orange (#FF8200)** is used for primary actions and highlights, symbolizing commerce and energy. **Secondary Green (#009E49)** is reserved for "Success" states, completed payments, and growth metrics, reinforcing a sense of prosperity. 

A deep **Neutral (#1A1C1E)** provides high-contrast legibility for text, while a crisp **White** and light off-white background ensure the interface remains clean under the varied lighting conditions of a retail environment. A tertiary "Finance Blue" is used sparingly for informational icons and links to maintain a professional, banking-grade atmosphere.

## Typography
This design system utilizes **Public Sans** across all levels to ensure maximum accessibility and a clean, institutional feel. As a neutral, geometric sans-serif, it provides the "official" tone necessary for a financial tool. 

Hierarchy is established through significant weight variance. Large "Display" and "Headline" sizes are used for monetary totals and primary navigation, ensuring they are readable from a distance behind a counter. "Label" styles use slightly increased letter spacing and semi-bold weights to remain legible even at small sizes on mobile POS handhelds.

## Layout & Spacing
The layout follows a **Fluid Grid** model optimized for the two primary POS form factors: 10-inch tablets and 5-inch handheld devices. On tablets, a 12-column grid is used with a persistent right-hand "Cart" sidebar. On mobile handhelds, a single-column stacked layout is employed.

The spacing rhythm is built on an **8px base unit**. This ensures consistent alignment and enough touch-target padding (minimum 44px) for busy merchants. Generous margins (24px-32px) on larger screens prevent the UI from feeling cluttered, maintaining the "premium" positioning of the tool.

## Elevation & Depth
Depth is conveyed using **Tonal Layers** supplemented by **Ambient Shadows**. Surfaces are tiered to represent the priority of information:
- **Level 0 (Background):** The base canvas in light gray.
- **Level 1 (Cards/Containers):** Pure white surfaces with a very soft, diffused 4% opacity shadow to lift them slightly.
- **Level 2 (Modals/Popovers):** Higher contrast shadows (12% opacity) with a 16px blur to pull critical actions (like "Confirm Payment") to the absolute foreground.

This approach creates a clear spatial mental model for the merchant: the product catalog sits on the bottom layer, while the active transaction or "Cart" sits on the middle layer.

## Shapes
The design system employs a **Rounded (8px)** shape language. This provides a modern, friendly feel that is more approachable than sharp corners, yet remains professional enough for a B2B financial application. 

Buttons and input fields use the standard 8px radius. Larger containers, such as product cards or receipt summaries, may scale up to 16px (rounded-lg) to emphasize their role as distinct content blocks. This consistent softening of the UI helps the technology feel "human-centric" and easy to use.

## Components
- **Buttons:** Primary buttons use the Orange #FF8200 background with White text. Success buttons use Green #009E49. All buttons feature a 56px height for tablet and 48px for mobile to ensure high "tapability" in fast environments.
- **Input Fields:** Use a subtle 1px border in mid-gray, which thickens and changes to Orange on focus. Labels are always persistent above the field for clarity.
- **Cards:** Product cards feature a top-aligned image, a bold price in the bottom right, and a subtle "Add" button.
- **Chips:** Used for filtering categories (e.g., "Food," "Electronics"). Unselected chips have a light gray fill; selected chips use a Primary Orange outline and text.
- **Lists:** Transaction history lists use high-contrast text for amounts and secondary-colored (Green) text for "Success" statuses.
- **Cart Component:** A persistent vertical container on the right side of tablet layouts, featuring a clear "Total" display in Display-LG typography for visibility to both merchant and customer.
- **Payment Success State:** A full-screen overlay utilizing the Secondary Green as a background or heavy accent to provide immediate psychological confirmation of a successful sale.