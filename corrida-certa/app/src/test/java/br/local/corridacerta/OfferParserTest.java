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
}
