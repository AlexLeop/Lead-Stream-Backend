import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { api } from '../api';
import type { PlatformBranding } from '../types';

interface BrandingContextType {
  branding: PlatformBranding;
  refreshBranding: () => Promise<void>;
  updateBranding: (data: Partial<PlatformBranding>) => Promise<PlatformBranding>;
  isLoading: boolean;
}

const DEFAULT_BRANDING: PlatformBranding = {
  platform_name: 'LeadStream',
  logo_url_dark: '',
  logo_url_light: '',
  favicon_url: '',
  accent_color: '#3B82F6',
  primary_color: '#0F172A',
  support_email: 'suporte@leadstream.com.br',
  terms_url: '',
  privacy_url: '',
};

const BrandingContext = createContext<BrandingContextType>({
  branding: DEFAULT_BRANDING,
  refreshBranding: async () => {},
  updateBranding: async () => DEFAULT_BRANDING,
  isLoading: false,
});

export const BrandingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [branding, setBranding] = useState<PlatformBranding>(DEFAULT_BRANDING);
  const [isLoading, setIsLoading] = useState(false);

  const applyBrandingToDOM = useCallback((brand: PlatformBranding) => {
    // 1. Dynamic document title
    if (brand.platform_name) {
      document.title = brand.platform_name;
    }

    // 2. CSS custom variables for accent and primary styling
    const root = document.documentElement;
    if (brand.accent_color) {
      root.style.setProperty('--color-accent', brand.accent_color);
    }
    if (brand.primary_color) {
      root.style.setProperty('--color-primary', brand.primary_color);
    }

    // 3. Dynamic favicon if configured
    if (brand.favicon_url) {
      let link = document.querySelector("link[rel~='icon']") as HTMLLinkElement | null;
      if (!link) {
        link = document.createElement('link');
        link.rel = 'icon';
        document.head.appendChild(link);
      }
      link.href = brand.favicon_url;
    }
  }, []);

  const refreshBranding = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await api.branding();
      if (data && data.platform_name) {
        setBranding(data);
        applyBrandingToDOM(data);
      }
    } catch {
      // Fallback cleanly without breaking rendering
    } finally {
      setIsLoading(false);
    }
  }, [applyBrandingToDOM]);

  const updateBrandingHandler = useCallback(
    async (data: Partial<PlatformBranding>): Promise<PlatformBranding> => {
      const updated = await api.updateBranding(data);
      setBranding(updated);
      applyBrandingToDOM(updated);
      return updated;
    },
    [applyBrandingToDOM]
  );

  useEffect(() => {
    refreshBranding();
  }, [refreshBranding]);

  return (
    <BrandingContext.Provider
      value={{
        branding,
        refreshBranding,
        updateBranding: updateBrandingHandler,
        isLoading,
      }}
    >
      {children}
    </BrandingContext.Provider>
  );
};

export const useBranding = () => useContext(BrandingContext);
