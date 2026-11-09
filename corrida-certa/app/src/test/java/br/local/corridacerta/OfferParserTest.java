package br.local.corridacerta;

import static org.junit.Assert.*;
import org.junit.Test;

public class OfferParserTest {
    @Test public void uberNormal() {
        String t = "Plus\nPagamento no app\nR$14,80\nR$2,21/km\nPreço x1,3\nR$2,58\n4,93\n+999 corridas\n"
                + "10min (1,8km)\nClínica Visão, Rua Cel. Bordini, 414\n19min (4,9km)\nVia Imperatore, 509";
        OfferParser.Offer o = OfferParser.parse(t);
        assertNotNull(o);
        assertEquals(14.80, o.value, 1e-9);
        assertEquals(6.7, o.totalKm(), 1e-9);
        assertEquals(2.21, o.perKm(), 0.005);
        assertEquals(30.62, o.perHour(), 0.005);
        assertFalse(o.bundle);
    }
    @Test public void uberPacote() {
        String t = "UberX (2)\nExclusivo\nR$ 20,08\n4,88\n4,82\n4 min (1.1 km)\nRua Carlos Gomes\n"
                + "1 desembarque, 1 viagem (3 minutos de distância)\n34 minutos (11.2 km)\nR. Vera Cruz\nPacote de viagens\nAceitar 2 viagens";
        OfferParser.Offer o = OfferParser.parse(t);
        assertNotNull(o);
        assertTrue(o.bundle);
        assertEquals(12.3, o.totalKm(), 1e-9);
        assertEquals(38, o.totalMin(), 1e-9);
    }
    @Test public void ignoraValorJaCalculado() {
        OfferParser.Offer o = OfferParser.parse("R$ 2,21/km\nR$ 30,62/hr\nR$ 14,80\n5 min (2 km)\n10 min (3 km)");
        assertEquals(14.80, o.value, 1e-9);
    }
    @Test public void horasEMetros() {
        OfferParser.Offer o = OfferParser.parse("R$ 80,00\n2 min (350 m)\n1 h 5 min (30,5 km)");
        assertEquals(30.85, o.totalKm(), 1e-9);
        assertEquals(67, o.totalMin(), 1e-9);
    }
    @Test public void semCardRetornaNull() {
        assertNull(OfferParser.parse("Você está online\nR$ 12,00 hoje"));
        assertNull(OfferParser.parse(null));
    }

    @Test public void card99() {
        OfferParser.Offer o = OfferParser.parse("Pgto. no app\nR$8,90\nR$1,58/km\nR$3,34 Tarifa base dinâmica incl.\n4,73 16 corridas\n"
                + "6 min (1,2 km)\nRua Barão do Triunfo, 707\n13 min (4,4 km)\nRua Garibaldi, 712");
        assertNotNull(o);
        assertEquals(8.90, o.value, 1e-9);
        assertEquals(5.6, o.totalKm(), 1e-9);
        assertEquals(1.59, o.perKm(), 0.005);
        assertEquals(28.11, o.perHour(), 0.005);
    }
    @Test public void ocrComErrosComuns() {
        OfferParser.Offer o = OfferParser.parse("RS8,90\n6 min [1,2 km)\n13 min (4,4 km]");
        assertNotNull(o);
        assertEquals(5.6, o.totalKm(), 1e-9);
    }

    @Test public void destinoUber() {
        OfferParser.Offer o = OfferParser.parse("UberX\nR$ 10,36\n6 min (2.4 km)\nRua Henrique Fraeb, Partenon, Porto Alegre\n13 minutos (5.7 km)\n"
                + "Av. Fábio Araújo Santos, 1188, Nonoai, Porto Alegre\nTenho interesse");
        assertEquals("Av. Fábio Araújo Santos, 1188, Nonoai, Porto Alegre", o.destination);
    }
    @Test public void destinoQuebradoPeloOcr() {
        OfferParser.Offer o = OfferParser.parse("R$ 7,04\n5 min (1.3 km)\nPraça X, Santana\n9 minutos (3.3 km)\n"
                + "Av. Aureliano de Figueiredo Pinto, 105 - Bairro, Praia de Belas,\nPorto Alegre\nTenho interesse");
        assertEquals("Av. Aureliano de Figueiredo Pinto, 105 - Bairro, Praia de Belas, Porto Alegre", o.destination);
    }
    @Test public void destino99() {
        OfferParser.Offer o = OfferParser.parse("R$8,90\n6 min (1,2 km)\nRua Barão do Triunfo, 707, Azenha\n13 min (4,4 km)\nRua Garibaldi, 712, Floresta\nTentando encontrar");
        assertEquals("Rua Garibaldi, 712, Floresta", o.destination);
    }

    @Test public void ignoraTextoDeInterfaceNoDestino() {
        OfferParser.Offer o = OfferParser.parse("UberX\nR$ 18,25\nEst. de R$1,5/km\n5 min (2.0 km)\nRua Pedro Alves, Centro\n"
                + "14 minutos (7.2 km)\nFiltro avançado\nRua Dom Pedro II, 1240, Higienópolis, Porto Alegre\nTenho interesse");
        assertEquals("Rua Dom Pedro II, 1240, Higienópolis, Porto Alegre", o.destination);
    }
    @Test public void semEnderecoClaroRetornaNull() {
        OfferParser.Offer o = OfferParser.parse("R$ 28,90\n4 min (1,0 km)\n20 min (9,0 km)\nFiltro avançado");
        assertNull(o.destination);
    }
    @Test public void enderecoNaMesmaLinhaDoTrecho() {
        OfferParser.Offer o = OfferParser.parse("R$ 9,00\n3 min (1 km)\n10 min (4 km) Rua das Flores, 55, Centro");
        assertEquals("Rua das Flores, 55, Centro", o.destination);
    }

    @Test public void bairros() {
        assertEquals("Nonoai", OfferParser.region("Av. Fábio Araújo Santos, 1188, Nonoai, Porto Alegre"));
        assertEquals("Floresta", OfferParser.region("Rua Garibaldi, 712, Floresta"));
        assertEquals("Praia de Belas", OfferParser.region("Av. Aureliano de Figueiredo Pinto, 105 - Bairro, Praia de Belas, Porto Alegre"));
        assertEquals("Praia de Belas", OfferParser.region("Rua Manoelito de Ornellas, 55/1601 - Praia de Belas"));
        assertEquals("Bom Fim", OfferParser.region("Rua Irmão José Otão, 11 - Bom Fim, Porto Alegre - RS, 90035-060"));
        assertNull(OfferParser.region("Avenida Francisco Trein,596"));
        assertNull(OfferParser.region("Rua Pedro Ivo, 362"));
        assertNull(OfferParser.region(null));
    }
    @Test public void embarqueEDestino() {
        OfferParser.Offer o = OfferParser.parse("UberX\nR$ 10,36\n6 min (2.4 km)\nRua Henrique Fraeb, Partenon, Porto Alegre\n13 minutos (5.7 km)\n"
                + "Av. Fábio Araújo Santos, 1188, Nonoai, Porto Alegre\nTenho interesse");
        assertEquals("Rua Henrique Fraeb, Partenon, Porto Alegre", o.pickupAddress);
        assertEquals("Partenon", OfferParser.region(o.pickupAddress));
        assertEquals("Nonoai", OfferParser.region(o.destination));
    }
}
