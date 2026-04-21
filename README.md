# ISV Delivery

Plataforma de delivery local para pequenas cidades do Brasil, comecando por **Tarumirim (MG)**.

## Visao

Delivery local simples, rapido e intuitivo, com taxa menor que os grandes players. Focado em cidades pequenas onde iFood/Rappi nao operam bem.

Spec completa vive no vault do Obsidian em `C:\Users\henri\Documents\My second mind\Projetos\ISV Delivery\`.

## Stack

| Camada | Tech |
|---|---|
| Mobile cliente + entregador | Flutter |
| Painel lojista + admin | Next.js |
| Backend | Python + FastAPI |
| Banco | PostgreSQL |
| Cache/filas | Redis |
| Hospedagem | Railway |
| Pagamentos | Pagar.me |
| Mapas | Google Maps APIs |
| Notificacoes | Firebase + APNs |

## Estrutura

```
delivery/
├── backend/          # FastAPI
├── apps/
│   ├── customer/    # App do cliente (Flutter)
│   └── driver/      # App do entregador (Flutter)
├── web/
│   ├── merchant/    # Painel do lojista (Next.js)
│   └── admin/       # Painel administrativo (Next.js)
├── docs/            # Documentacao tecnica local
├── .github/         # CI/CD
└── scripts/         # Scripts utilitarios
```

## Setup local

(A preencher conforme cada subprojeto for criado)

## Status

Em desenvolvimento — fase de setup

## Licenca

Proprietario. Todos os direitos reservados.
