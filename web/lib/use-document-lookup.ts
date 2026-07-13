"use client";

import { useState } from "react";

import { lookupCepAction, lookupCnpjAction } from "@/app/actions";
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

/** Autopreenche endereço a partir do CEP (ViaCEP). Padrão único para todos os cadastros do tenant. */
export function useCepLookup(onFound: (fields: AddressFields) => void) {
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  async function handleBlur(cep: string) {
    setNotFound(false);
    if (!cep || !isValidCEP(cep)) return;
    setLoading(true);
    const result = await lookupCepAction(cep);
    setLoading(false);
    if (!result.ok) {
      setNotFound(true);
      return;
    }
    onFound({
      address_street: result.address_street,
      address_neighborhood: result.address_neighborhood,
      address_city: result.address_city,
      address_state: result.address_state,
    });
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
    const result = await lookupCnpjAction(doc);
    setLoading(false);
    if (!result.ok) {
      if (result.rateLimited) setRateLimited(true);
      else setNotFound(true);
      return;
    }
    onFound({
      name: result.name,
      trade_name: result.trade_name,
      email: result.email,
      phone: result.phone,
      address_street: result.address_street,
      address_number: result.address_number,
      address_complement: result.address_complement,
      address_neighborhood: result.address_neighborhood,
      address_city: result.address_city,
      address_state: result.address_state,
      address_zip: result.address_zip,
    });
  }

  return { loading, notFound, rateLimited, handleBlur };
}
