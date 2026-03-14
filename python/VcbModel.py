from HiggsAnalysis.CombinedLimit.PhysicsModel import *


class VcbModel(PhysicsModel):
    def __init__(self):
        PhysicsModel.__init__(self)

    def doParametersOfInterest(self):
        """Create POI and other parameters, and define the POI set."""
        #self.modelBuilder.doVar('BR[0,0,0.005]');
        self.modelBuilder.doVar('r[1,-1,2.5]');
        self.modelBuilder.doSet('POI','r')
        #self.modelBuilder.doVar('sqrtBR[0,0.00001,1]');
        #self.modelBuilder.doSet('POI','sqrtBR')
        isVcbModel2 = True  # consider H+(80GeV) as W+(80GeV) and find the best fit of Vcb
        self.modelBuilder.factory_('expr::Scaling_BR("@0", r)')
        self.modelBuilder.factory_('expr::Scaling_WtoCB("@0", Scaling_BR)')
        self.modelBuilder.factory_('expr::Scaling_TTLJ_4("(1-@0*0.00166464)", Scaling_BR)')#this should scaled by 1-Vcb**2*r


        self.processScaling = {
                'WtoCB':'WtoCB',
                'TTLJ_4':'TTLJ_4',
                'TTLJ_Vcb':'WtoCB'
                }

        self.modelBuilder.out.Print()

    def getYieldScale(self,bin,process):

        for prefix, model in self.processScaling.items():
            if prefix in process:
                print('expression Scaling_%s is assigned to process %s' % (prefix,process))
                return 'Scaling_'+model

        return 1

class VcbModel2(PhysicsModel):
    def __init__(self):
        PhysicsModel.__init__(self)

    def doParametersOfInterest(self):
        """Create POI and other parameters, and define the POI set."""
        #self.modelBuilder.doVar('BR[0,0,0.005]');
        self.modelBuilder.doVar('r[1,0.,2.5]');
        self.modelBuilder.doSet('POI','r')
        #self.modelBuilder.doVar('sqrtBR[0,0.00001,1]');
        #self.modelBuilder.doSet('POI','sqrtBR')
        isVcbModel2 = True  # consider H+(80GeV) as W+(80GeV) and find the best fit of Vcb
        self.modelBuilder.factory_('expr::Scaling_BR("@0*@0", r)')
        self.modelBuilder.factory_('expr::Scaling_WtoCB("@0", Scaling_BR)')
        self.modelBuilder.factory_('expr::Scaling_TTLJ_4("(1-@0*0.00166464)", Scaling_BR)')#2*0.304079789/365.34


        self.processScaling = {
                'WtoCB':'WtoCB',
                'TTLJ_4':'TTLJ_4',
                'TTLJ_Vcb':'WtoCB'
                }

        self.modelBuilder.out.Print()

    def getYieldScale(self,bin,process):


        for prefix, model in self.processScaling.items():
            if prefix in process:
                print('expression Scaling_%s is assigned to process %s' % (prefix,process))
                return 'Scaling_'+model

        return 1

brVcbModel = VcbModel()
brVcbModel2 = VcbModel2()