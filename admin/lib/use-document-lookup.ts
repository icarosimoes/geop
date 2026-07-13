"use client";

import { useState } from "react";
import { isValidCEP, isValidCNPJ, onlyDigits } from "@/lib/validators";

export interface AddressFields {
  address_street?: string;
  address_number?: string;
  address_complement?: string;
  address_neighborhood?: string;
  address_city?: string;
  address_state?: string;
  address_zip?: string;
}

export interface CnpjFields extends AddressFields {
  name?: string;
  trade_name?: string;
  email?: string;
  phone?: string;
}

async function fetchCep(cep: string): Promise<AddressFields | null> {
  const digits = onlyDigits(cep);
  if (digits.length !== 8) return null;
  try {
    const res = await fetch(`https://viacep.com.br/ws/${digits}/json/`, { cache: "no-store" });
    if (!res.ok) return null;
    const data = await res.json();
    if (data.erro) return null;
    return {
      address_street: data.logradouro || undefined,
      address_neighborhood: data.bairro || undefined,
      address_city: data.localidade || undefined,
      address_state: data.uf || undefined,
    };
  } catch {
    return null;
  }
}

async function fetchCnpj(cnpj: string): Promise<{ fields: CnpjFields | null; rateLimited: boolean }> {
  const digits = onlyDigits(cnpj);
  if (digits.length !== 14) return { fields: null, rateLimited: false };
  try {
    const res = await fetch(`https://brasilapi.com.br/api/cnpj/v1/${digits}`, { cache: "no-store" });
    if (res.status === 429) return { fields: null, rateLimited: true };
    if (!res.ok) return { fields: null, rateLimited: false };
    const data = await res.json();
    return {
      rateLimited: false,
      fields: {
        name: data.razao_social || undefined,
        trade_name: data.nome_fantasia || undefined,
        email: data.email || undefined,
        phone: data.ddd_telefone_1 || undefined,
        address_street: data.logradouro || undefined,
        address_number: data.numero || undefined,
        address_complement: data.complemento || undefined,
        address_neighborhood: data.bairro || undefined,
        address_city: data.municipio || undefined,
        address_state: data.uf || undefined,
        address_zip: data.cep || undefined,
      },
    };
  } catch {
    return { fields: null, rateLimited: false };
  }
}

/** Autopreenche endereço a partir do CEP (ViaCEP). Padrão único para todos os cadastros da plataforma. */
export function useCepLookup(onFound: (fields: AddressFields) => void) {
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  async function handleBlur(cep: string) {
    setNotFound(false);
    if (!cep || !isValidCEP(cep)) return;
    setLoading(true);
    const result = await fetchCep(cep);
    setLoading(false);
    if (!result) {
      setNotFound(true);
      return;
    }
    onFound(result);
  }

  return { loading, notFound, handleBlur };
}

/** Autopreenche razão social, nome fantasia e endereço a partir do CNPJ (BrasilAPI). */
export function useCnpjLookup(onFound: (fields: CnpjFields) => void) {
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [rateLimited, setRateLimited] = useState(false);

  async function handleBlur(doc: string) {
    setNotFound(false);
    setRateLimited(false);
    const digits = onlyDigits(doc);
    if (digits.length !== 14 || !isValidCNPJ(doc)) return;
    setLoading(true);
    const { fields, rateLimited: limited } = await fetchCnpj(doc);
    setLoading(false);
    if (!fields) {
      if (limited) setRateLimited(true);
      else setNotFound(true);
      return;
    }
    onFound(fields);
  }

  return { loading, notFound, rateLimited, handleBlur };
}
