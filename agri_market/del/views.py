"""
Vues pour la gestion des produits
Auteur: Dufort (avec contribution Pavel)
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from django.db.models import Sum
from .models import Utilisateur, Produit, Commande, LigneCommande
from .services_produit import ServiceProduit, ServiceCategorie
from django.contrib.admin.views.decorators import staff_member_required
from .services_panier import ServicePanier

# =========================
# GESTION DU PANIER
# =========================

@login_required
def voir_panier(request):
    """Afficher le panier du client"""
    if request.user.role != 'CLIENT':
        messages.error(request, "Seuls les clients peuvent avoir un panier")
        return redirect('liste_produits')
    
    details = ServicePanier.obtenir_panier_avec_details(request.user.id)
    
    context = {
        'panier': details['panier'],
        'lignes': details['lignes'],
        'vendeurs': details['vendeurs'],
        'nombre_articles': details['nombre_articles'],
        'montant_total': details['montant_total'],
    }
    
    return render(request, 'agri_market/panier/voir_panier.html', context)


@login_required
@require_http_methods(["POST"])
def ajouter_au_panier(request, produit_id):
    """Ajouter un produit au panier"""
    if request.user.role != 'CLIENT':
        messages.error(request, "Seuls les clients peuvent ajouter au panier")
        return redirect('liste_produits')
    
    try:
        quantite = int(request.POST.get('quantite', 1))
        ServicePanier.ajouter_au_panier(request.user.id, produit_id, quantite)
        messages.success(request, "Produit ajouté au panier avec succès !")
    except (ValidationError, ValueError) as e:
        messages.error(request, str(e))
    
    return redirect('voir_panier')


@login_required
@require_http_methods(["POST"])
def modifier_quantite_panier(request, ligne_id):
    """Modifier la quantité d'un article dans le panier"""
    try:
        nouvelle_quantite = int(request.POST.get('quantite', 1))
        ServicePanier.modifier_quantite(request.user.id, ligne_id, nouvelle_quantite)
        messages.success(request, "Quantité mise à jour")
    except (ValidationError, ValueError) as e:
        messages.error(request, str(e))
    
    return redirect('voir_panier')


@login_required
@require_http_methods(["POST"])
def retirer_du_panier(request, ligne_id):
    """Retirer un produit du panier"""
    try:
        ServicePanier.retirer_du_panier(request.user.id, ligne_id)
        messages.success(request, "Article retiré du panier")
    except ValidationError as e:
        messages.error(request, str(e))
    
    return redirect('voir_panier')


@login_required
@require_http_methods(["POST"])
def vider_panier(request):
    """Vider complètement le panier"""
    ServicePanier.vider_panier(request.user.id)
    messages.success(request, "Panier vidé")
    return redirect('voir_panier')


@login_required
def valider_commande(request):
    """Valider la commande"""
    if request.method == 'POST':
        try:
            mode_retrait = request.POST.get('mode_retrait', 'LIVRAISON')
            adresse = request.POST.get('adresse_livraison', '')
            
            commande = ServicePanier.valider_commande(
                request.user.id,
                mode_retrait,
                adresse
            )
            
            messages.success(
                request,
                f"Commande #{commande.id} validée ! Les vendeurs ont été notifiés."
            )
            return redirect('mes_commandes')
            
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('voir_panier')
    
    # GET : afficher le formulaire de validation
    details = ServicePanier.obtenir_panier_avec_details(request.user.id)
    
    context = {
        'panier': details['panier'],
        'vendeurs': details['vendeurs'],
        'montant_total': details['montant_total'],
    }
    
    return render(request, 'agri_market/panier/valider_commande.html', context)


@login_required
def mes_commandes(request):
    """Liste des commandes du client"""
    if request.user.role != 'CLIENT':
        messages.error(request, "Accès réservé aux clients")
        return redirect('liste_produits')
    
    commandes = Commande.objects.filter(
        client=request.user
    ).exclude(
        statut='PANIER'
    ).prefetch_related('lignes__produit').order_by('-date_commande')
    
    context = {
        'commandes': commandes
    }
    
    return render(request, 'agri_market/client/mes_commandes.html', context)

@staff_member_required
def dashboard_admin(request):
    """Dashboard administrateur - accessible uniquement aux superusers"""
    from django.db.models import Count, Q
    
    # Statistiques
    stats = {
        'total_users': Utilisateur.objects.count(),
        'total_vendeurs': Utilisateur.objects.filter(role='VENDEUR').count(),
        'total_clients': Utilisateur.objects.filter(role='CLIENT').count(),
        'total_produits': Produit.objects.count(),
        'total_commandes': Commande.objects.exclude(statut='PANIER').count(),
        'commandes_attente': Commande.objects.filter(statut='EN_ATTENTE').count(),
        'commandes_payees': Commande.objects.filter(statut='PAYEE').count(),
        'commandes_livrees': Commande.objects.filter(statut='LIVREE').count(),
    }
    
    # Listes
    vendeurs = Utilisateur.objects.filter(role='VENDEUR').prefetch_related('produits').order_by('-date_joined')
    clients = Utilisateur.objects.filter(role='CLIENT').prefetch_related('commandes').order_by('-date_joined')
    commandes_recentes = Commande.objects.exclude(statut='PANIER').select_related('client').prefetch_related('lignes').order_by('-date_commande')[:20]
    
    context = {
        'stats': stats,
        'vendeurs': vendeurs,
        'clients': clients,
        'commandes_recentes': commandes_recentes,
    }
    
    return render(request, 'agri_market/admin/dashboard.html', context)

# =========================
# VUES PUBLIQUES (Catalogue)
# =========================
def home(request):
    """Page d'accueil du site"""
    return render(request, 'agri_market/home.html')

# =========================
# AUTHENTIFICATION
# =========================

from django.contrib.auth import authenticate, login, logout

def connexion(request):
    """Page de connexion"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenue {user.first_name} !")
            
            # Rediriger selon le rôle
            if user.role == 'VENDEUR':
                return redirect('mes_produits')
            else:
                return redirect('liste_produits')
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect")
    
    return render(request, 'agri_market/auth/login.html')


def deconnexion(request):
    """Déconnexion"""
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès")
    return redirect('home')


def inscription(request):
    """Page d'inscription"""
    if request.method == 'POST':
        try:
            # Récupérer les données
            username = request.POST.get('username')
            email = request.POST.get('email')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            role = request.POST.get('role')
            telephone = request.POST.get('telephone', '')
            nom_boutique = request.POST.get('nom_boutique', '')
            
            # Validations
            if password1 != password2:
                messages.error(request, "Les mots de passe ne correspondent pas")
                return render(request, 'agri_market/auth/inscription.html')
            
            if Utilisateur.objects.filter(username=username).exists():
                messages.error(request, "Ce nom d'utilisateur existe déjà")
                return render(request, 'agri_market/auth/inscription.html')
            
            if Utilisateur.objects.filter(email=email).exists():
                messages.error(request, "Cet email est déjà utilisé")
                return render(request, 'agri_market/auth/inscription.html')
            
            if role == 'VENDEUR' and not nom_boutique:
                messages.error(request, "Le nom de la boutique est obligatoire pour les vendeurs")
                return render(request, 'agri_market/auth/inscription.html')
            
            # Créer l'utilisateur
            user = Utilisateur.objects.create_user(
                username=username,
                email=email,
                password=password1,
                first_name=first_name,
                last_name=last_name,
                role=role,
                telephone=telephone,
                nom_boutique=nom_boutique if role == 'VENDEUR' else None
            )
            
            messages.success(request, "Compte créé avec succès ! Vous pouvez maintenant vous connecter.")
            return redirect('connexion')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création du compte : {str(e)}")
    
    return render(request, 'agri_market/auth/inscription.html')
        
def liste_produits(request):
    """
    Afficher tous les produits disponibles (page publique)
    """
    # Recherche et filtrage
    terme_recherche = request.GET.get('recherche', '')
    categorie_id = request.GET.get('categorie', '')
    
    if terme_recherche:
        produits = ServiceProduit.rechercher_produits(terme_recherche)
    elif categorie_id:
        produits = ServiceProduit.filtrer_par_categorie(categorie_id)
    else:
        produits = ServiceProduit.lister_tous_produits()
    
    categories = ServiceCategorie.lister_categories()
    
    context = {
        'produits': produits,
        'categories': categories,
        'terme_recherche': terme_recherche,
        'categorie_selectionnee': categorie_id
    }
    
    return render(request, 'agri_market/produits/liste.html', context)


def detail_produit(request, produit_id):
    """
    Afficher les détails d'un produit
    """
    try:
        produit = ServiceProduit.obtenir_produit(produit_id)
        
        # Produits similaires (même catégorie)
        produits_similaires = Produit.objects.filter(
            categorie=produit.categorie
        ).exclude(id=produit_id)[:4]
        
        context = {
            'produit': produit,
            'produits_similaires': produits_similaires
        }
        
        return render(request, 'agri_market/produits/detail.html', context)
        
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('liste_produits')


# =========================
# VUES VENDEUR (Gestion)
# =========================

@login_required
def mes_produits(request):
    """
    Lister les produits du vendeur connecté
    """
    # Vérifier que l'utilisateur est un vendeur
    if request.user.role != 'VENDEUR':
        messages.error(request, "Accès réservé aux vendeurs")
        return redirect('liste_produits')
    
    produits = ServiceProduit.lister_produits_vendeur(request.user.id)
    
    context = {
        'produits': produits
    }
    
    return render(request, 'agri_market/vendeur/mes_produits.html', context)


@login_required
def ajouter_produit(request):
    """
    Ajouter un nouveau produit
    """
    # Vérifier que l'utilisateur est un vendeur
    if request.user.role != 'VENDEUR':
        messages.error(request, "Accès réservé aux vendeurs")
        return redirect('liste_produits')
    
    if request.method == 'POST':
        try:
            # Récupérer les données du formulaire
            nom = request.POST.get('nom')
            description = request.POST.get('description', '')
            prix = float(request.POST.get('prix'))
            quantite = int(request.POST.get('quantite'))
            categorie_id = int(request.POST.get('categorie'))
            
            # Créer le produit via le service
            produit = ServiceProduit.creer_produit(
                vendeur_id=request.user.id,
                nom=nom,
                prix=prix,
                quantite=quantite,
                categorie_id=categorie_id,
                description=description
            )
            
            messages.success(request, f"Produit '{produit.nom}' ajouté avec succès !")
            return redirect('mes_produits')
            
        except (ValidationError, PermissionDenied) as e:
            messages.error(request, str(e))
        except ValueError:
            messages.error(request, "Veuillez vérifier les données saisies")
    
    # GET request ou erreur : afficher le formulaire
    categories = ServiceCategorie.lister_categories()
    
    context = {
        'categories': categories
    }
    
    return render(request, 'agri_market/vendeur/ajouter_produit.html', context)


@login_required
def modifier_produit(request, produit_id):
    """
    Modifier un produit existant
    """
    if request.user.role != 'VENDEUR':
        messages.error(request, "Accès réservé aux vendeurs")
        return redirect('liste_produits')
    
    try:
        produit = ServiceProduit.obtenir_produit(produit_id)
        
        # Vérifier que c'est bien le produit du vendeur
        if produit.vendeur.id != request.user.id:
            messages.error(request, "Vous ne pouvez modifier que vos propres produits")
            return redirect('mes_produits')
        
        if request.method == 'POST':
            # Récupérer les données
            donnees = {
                'nom': request.POST.get('nom'),
                'description': request.POST.get('description', ''),
                'prix': float(request.POST.get('prix')),
                'quantite': int(request.POST.get('quantite')),
                'categorie_id': int(request.POST.get('categorie'))
            }
            
            # Modifier le produit
            produit = ServiceProduit.modifier_produit(
                produit_id=produit_id,
                vendeur_id=request.user.id,
                **donnees
            )
            
            messages.success(request, f"Produit '{produit.nom}' modifié avec succès !")
            return redirect('mes_produits')
        
        # GET : afficher le formulaire pré-rempli
        categories = ServiceCategorie.lister_categories()
        
        context = {
            'produit': produit,
            'categories': categories
        }
        
        return render(request, 'agri_market/vendeur/modifier_produit.html', context)
        
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))
        return redirect('mes_produits')
    except ValueError:
        messages.error(request, "Données invalides")
        return redirect('mes_produits')


@login_required
@require_http_methods(["POST"])
def supprimer_produit(request, produit_id):
    """
    Supprimer un produit
    """
    if request.user.role != 'VENDEUR':
        messages.error(request, "Accès réservé aux vendeurs")
        return redirect('liste_produits')
    
    try:
        ServiceProduit.supprimer_produit(
            produit_id=produit_id,
            vendeur_id=request.user.id
        )
        
        messages.success(request, "Produit supprimé avec succès !")
        
    except (ValidationError, PermissionDenied) as e:
        messages.error(request, str(e))
    
    return redirect('mes_produits')
    
    
# =========================
# GESTION DES COMMANDES VENDEUR
# =========================

@login_required
def commandes_vendeur(request):
    """Liste des commandes reçues par le vendeur"""
    if request.user.role != 'VENDEUR':
        messages.error(request, "Accès réservé aux vendeurs")
        return redirect('liste_produits')
    
    from django.db.models import Sum, F
    
    # Filtrer par statut si demandé
    statut_filtre = request.GET.get('statut', '')
    
    # Récupérer toutes les commandes qui contiennent mes produits
    mes_produits_ids = Produit.objects.filter(vendeur=request.user).values_list('id', flat=True)
    
    commandes_query = Commande.objects.filter(
        lignes__produit_id__in=mes_produits_ids
    ).exclude(statut='PANIER').distinct().select_related('client').prefetch_related('lignes__produit')
    
    if statut_filtre:
        commandes_query = commandes_query.filter(statut=statut_filtre)
    
    commandes_query = commandes_query.order_by('-date_commande')
    
    # Préparer les données avec seulement mes lignes
    commandes_data = []
    for commande in commandes_query:
        mes_lignes = commande.lignes.filter(produit__vendeur=request.user)
        mon_total = sum(ligne.prix_unitaire * ligne.quantite for ligne in mes_lignes)
        
        commandes_data.append({
            'commande': commande,
            'mes_lignes': mes_lignes,
            'mon_total': mon_total
        })
    
    # Statistiques
    stats = {
        'en_attente': Commande.objects.filter(
            lignes__produit__vendeur=request.user,
            statut='EN_ATTENTE'
        ).distinct().count(),
        'payees': Commande.objects.filter(
            lignes__produit__vendeur=request.user,
            statut='PAYEE'
        ).distinct().count(),
        'expediees': Commande.objects.filter(
            lignes__produit__vendeur=request.user,
            statut='EXPEDIEE'
        ).distinct().count(),
        'livrees': Commande.objects.filter(
            lignes__produit__vendeur=request.user,
            statut='LIVREE'
        ).distinct().count(),
    }
    
    context = {
        'commandes': commandes_data,
        'stats': stats,
    }
    
    return render(request, 'agri_market/vendeur/commandes_recues.html', context)


@login_required
@require_http_methods(["POST"])
def changer_statut_commande(request, commande_id):
    """Changer le statut d'une commande (vendeur)"""
    if request.user.role != 'VENDEUR':
        messages.error(request, "Accès réservé aux vendeurs")
        return redirect('liste_produits')
    
    try:
        commande = Commande.objects.get(id=commande_id)
        nouveau_statut = request.POST.get('statut')
        
        # Vérifier que cette commande contient mes produits
        if not commande.lignes.filter(produit__vendeur=request.user).exists():
            messages.error(request, "Cette commande ne vous concerne pas")
            return redirect('commandes_vendeur')
        
        # Valider la transition de statut
        transitions_valides = {
            'EN_ATTENTE': ['PAYEE', 'ANNULEE'],
            'PAYEE': ['EXPEDIEE', 'ANNULEE'],
            'EXPEDIEE': ['LIVREE'],
        }
        
        if commande.statut in transitions_valides:
            if nouveau_statut in transitions_valides[commande.statut]:
                commande.statut = nouveau_statut
                commande.save()
                messages.success(request, f"Statut mis à jour: {commande.get_statut_display()}")
            else:
                messages.error(request, "Transition de statut invalide")
        else:
            messages.error(request, "Impossible de modifier ce statut")
            
    except Commande.DoesNotExist:
        messages.error(request, "Commande introuvable")
    
    return redirect('commandes_vendeur')


# =========================
# API AJAX (Optionnel)
# =========================

@login_required
def ajuster_stock_ajax(request, produit_id):
    """
    Ajuster le stock via AJAX
    """
    if request.method == 'POST' and request.user.role == 'VENDEUR':
        try:
            quantite_delta = int(request.POST.get('delta', 0))
            
            produit = ServiceProduit.ajuster_stock(
                produit_id=produit_id,
                quantite_delta=quantite_delta
            )
            
            return JsonResponse({
                'success': True,
                'nouvelle_quantite': produit.quantite,
                'message': 'Stock mis à jour'
            })
            
        except (ValidationError, ValueError) as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'}, status=405)
