原始安装的prompt

我现在正在构建一套harness的AI协同开发的工作流，我已经将一份harness手册放进来了，然后我的核心认知和理解，也写到conding-soul里了，现在需要你充分吸收，而且以我的soul为核心，harness手册为辅助，帮我梳理一套完整的工作流搭建的步骤和内容，后续需要你帮我在本地搭建好。搭建肯定包括一套skill+agent+hook+全局claude.md，然后一份核心工作流使 用说明。你先帮我梳理一下根据我的soul，工作流应该包含哪些组件和内容，在这个里面也有大量的别人的实践几类的一套skill+agent+hoot：「outerSpace/source」，肯定不是全盘吸收，少就是多，精准比量大更重要！因为当前AI大模型本质的根本痛点是上下文限制，一味把各种好的内容都放进来，反而不会好。我的soul里的每一条，都需要包含的，都是很核心的内容了，都需要落实的。此外，你也需要先摸排下我的全局claude配置都有些啥设置了，检查是否满足Soul，一定是以Soul为准构建一切的。注意我指定一个：我原先的全局 Skills都太老了，一个都不要了，skill生成器的skill要Anthropic的skills里的skill-creator。其他的你都从source里按必要的去拿即可。你先理解下我要干嘛，  阐述给我听，我看我俩认知是不是达成一致了？

————————
搭建完后（可安装的文件也生成了）还做了一件事情：

我的source文件夹里都是各种开源的，好用的skill，hook，agent等。我需要你给我搞  
个软连接，放到claude的全局里，这样的话以后都能读到，我可以让claudecode按我具体  
的项目，把项目所需要的skill等都放到项目级别里
明确一下，其实很简单，我只希望将source整个都软连接或者拷贝也行吧，只是为了以  
后方便我用，以后我的使用场景会是：“我需要某个能力，做某件事情，你去source里找找 
有没有对应的agent，工具或者技能，然后放到项目级别里”
两个待你确认的点

  1.  软链接名字 用  source-library  可以吗？还是你想叫别的（比如
   library 、 toolbox 、 source ）？
  2.  要不要顺手在   ~/.claude/CLAUDE.md  加那段索引 ？不加也行，只是将来每个 session
   都得你主动提"去 source 里翻"；加了就能全局触发。

  两个问题回复我，就动手。

❯  叫library吧，以后有好的项目我照样可以往里面继续加。全局claude.md里先不加，以  
后我自己说，去library里找，再去找，只要加一段：“如果用户需要去找一些适用于claud 
ecode的工具，或者说了去library里找，可以去library（绝对路径）里找。”就行

  我想了想，还是复制一份过去吧，软连接也不要了，以后要加好的工具进去也方便，而  
且还不容易丢失，不然放别的地方那天误删除了呢 

好。计划 3 步，先跟你对齐：                                                   
                                                                              
  1.  删除 现有软链接  ~/.claude/library                                            
  2.  拷贝   source/  整个目录到  ~/.claude/library/ （真实副本）                     
  3.  更新   ~/.claude/CLAUDE.md  里那段索引的措辞：去掉"软链接"字样，把            
   ~/.claude/library/  作为主路径                                                 
                                                                                
  ⚠️  一个你需要知道的后果：以后 source 里的上游项目（比如                       
  agent-toolkit、everything-claude-code）更新时，不会自动同步到              
   ~/.claude/library ，需要你手动重拷贝或手动                                     
  merge。 你现在要的正是这个行为 （稳定快照 > 自动更新），对吗？               

  确认就动手。                                                                  
  
❯  没错，要更新我直接来这里更新，或者贴了地址，让agent帮我更新就好。

                                                                                
  1. ✅ 软链接已删除                                                            
  2. ✅  source/  完整拷贝到  ~/.claude/library/ （三个子库： Anthropic的skills 、 agen
   t-toolkit 、 everything-claude-code ）                                           
  3. ✅  CLAUDE.md  索引简化为"去  ~/.claude/library/  里找"                        
               
  以后要更新某个子库，你直接在  ~/.claude/library/  里操作，或者贴 repo 地址让    
  agent 帮你覆盖对应子目录即可。
