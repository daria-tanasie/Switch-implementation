# Switch-implementation

Am inceput prin citirea fisierelor de config, linie cu linie. Retinem prioritatea, iar
intefetele le vom pastra sub forma unui dictionar unde stocam si felul porturilor(daca 
sunt Trunk sau Access). Vom pastra intr un vector si tipul de start al porturilor pentru
STP (daca este Access nu avem un tip, asa ca punem X, iat pentru Trunk punem D pentru designated).

    Dupa citire, cream si o structura BPDU care va stoca informatiile pentru switch ul curent.
Pornim apoi threadul pentru a trimite la fiecare secunda un pachet BPDU al switchului curent.

    Functia send_bpdu_every_sec():
    Am implementat aceasta functie conform indicatiilor din tema. Daca suntem root bridge,
trimitem un pachet BPDU pe care il cream cu ajutorul functiei create_bpdu_packet() catre toate
interfetele switchului daca sunt de tip trunk (acest pachet va avea lungimea 29 pt protocolul
implementat).

    Functia create_bpdu_packet():
    Aici vom face un pachet de tip BPDU cu informatiile si lungimile puse in enunt.
Am folosit doar root bridge idul, bridge id ul, root path costul si port id ul, fiind
singurele de care era nevoie in algoritmul de STP. Transformam in bytes datele si La
final asamblam pachetul.

    In continuare, in while(), incepem sa primim pachete pe care le parsam. Dupa, vom adauga
interfata pe care am primit pachetul in tabela mac care este un dictionar sursa - interafata.
    Verificam sa vedem daca pachetul a venit de pe un port Access. In caz afirmativ, inseamna ca
vlan ul nu este setat si trebuie sa modificam pachetul data, actualizam lungimea si setam vlan_id ul.

    Verificam acum daca dest_mac este o adresa unicast cu ajutorul functiei is_unicast().
Aceasta verifica daca al 2lea element este par, iar in caz pozitiv, avem o adresa unicast.
    Daca destinatia se afla in tabela mac si portul destinatie nu este blocat, mai trebuie
doar sa vedem ce tip de port avem. Daca este trunk, trimitem pachetul mai departe, iar daca
este Access si avem o potrivire pentru vlan, scoatem bucata de vlan din pachet si il trimitem la 
destinatie.
    Dace nu avem destinatia in tabela, trimitem pachetul pe toate interfetele, in afara
de cea pe unde a venit pachetul, facand verificarile de port trunk/access.

    Daca avem o adresa multicast, putem avea 2 cazuri: fie este un pachet BPDU, fie un pachet normal.
Acest lucru il verificam in functie de adresa mac destinatie (01:80:C2:00:00:00 pentru BPDU).
    Daca avem BPDU, parsam pachetul primit cu ajutorul functiei parse_bpdu_packet() care preia 
informatiile din pachet de unde incepe cadrul BPDU sub forma de bytes, le transforma in int si
creeaza un nou pachet BPDU cu informatiile primite. 
    In continuare, vom aplica algoritmul descris in enunt, verificand daca se schimba root bridge ul,
facand schimbarile necesare. Daca gasim un nou root, schimbam informatiile din structura BPDU
a switchului curent si trimitem un noua structura bpdu catre celelalte switchuri.
    Daca avem acelasi root, actualizam calea astfel incat sa fie cea mai
scurta si interfetele de legatura cu root ul sa fie designated.
    La final, daca suntem root, setam porturile trunk pe designated.

    Daca nu avem un pachet BPDU, vom aplica aceasi pasi ca mai sus pentru a trimite pachetul
catre toate interfetele, avand un pachet trimis cu destinatie multicast.
